import { spawn } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { app, BrowserWindow, dialog, session, shell } from "electron";

import {
  DESKTOP_HEADER,
  createDesktopToken,
  desktopDatabaseUrl,
  isBackendUrl,
  parseListeningEvent,
  selectPreferredPort,
} from "./runtime.mjs";

const APP_NAME = "知域引擎";
const STARTUP_TIMEOUT_MS = 60_000;
const SHUTDOWN_TIMEOUT_MS = 5_000;
const DESKTOP_DIR = resolve(fileURLToPath(new URL(".", import.meta.url)));
const PROJECT_ROOT = resolve(DESKTOP_DIR, "..");

app.setName(APP_NAME);
// 自动化测试可显式隔离用户数据；正常用户始终使用 Windows AppData 目录。
const userDataDirectory = process.env.ZHIYU_USER_DATA_DIR?.trim() || join(app.getPath("appData"), APP_NAME);
app.setPath("userData", userDataDirectory);

let mainWindow = null;
let backendProcess = null;
let backendPort = null;
let backendToken = null;
let isQuitting = false;
let backendExpectedToExit = false;

function resourcePath(...parts) {
  return app.isPackaged
    ? join(process.resourcesPath, ...parts)
    : join(PROJECT_ROOT, ...parts);
}

function appAssetPath(...parts) {
  return join(DESKTOP_DIR, ...parts);
}

function backendExecutablePath() {
  return app.isPackaged
    ? resourcePath("backend", "zhiyu-backend.exe")
    : resourcePath("desktop", "out", "backend", "zhiyu-backend.exe");
}

function backendUrl(pathname = "/") {
  if (!backendPort) throw new Error("桌面后端尚未就绪");
  return `http://127.0.0.1:${backendPort}${pathname}`;
}

function getUserDirectories() {
  const userData = app.getPath("userData");
  const dataDir = join(userData, "data");
  const logsDir = join(userData, "logs");
  mkdirSync(dataDir, { recursive: true });
  mkdirSync(logsDir, { recursive: true });
  return { userData, dataDir, logsDir };
}

function configureSession() {
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  session.defaultSession.webRequest.onBeforeSendHeaders((details, callback) => {
    if (backendPort && backendToken && isBackendUrl(details.url, backendPort)) {
      details.requestHeaders[DESKTOP_HEADER] = backendToken;
    }
    callback({ requestHeaders: details.requestHeaders });
  });
}

function createWindow() {
  const window = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    show: false,
    title: APP_NAME,
    icon: appAssetPath("assets", "icon.ico"),
    backgroundColor: "#F7FAFC",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: appAssetPath("preload.cjs"),
    },
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://")) void shell.openExternal(url);
    return { action: "deny" };
  });
  window.webContents.on("will-navigate", (event, url) => {
    if (!backendPort || !isBackendUrl(url, backendPort)) event.preventDefault();
  });
  window.once("ready-to-show", () => window.show());
  window.on("closed", () => {
    if (mainWindow === window) mainWindow = null;
  });
  window.loadFile(appAssetPath("loading.html"));
  return window;
}

function waitForListeningEvent(child) {
  return new Promise((resolvePromise, rejectPromise) => {
    let outputBuffer = "";
    const timeout = setTimeout(() => rejectPromise(new Error("桌面后端启动超时")), STARTUP_TIMEOUT_MS);
    const finish = (error, port) => {
      clearTimeout(timeout);
      child.stdout?.off("data", onData);
      child.off("error", onError);
      child.off("exit", onExit);
      error ? rejectPromise(error) : resolvePromise(port);
    };
    const onData = (chunk) => {
      outputBuffer += chunk.toString();
      const lines = outputBuffer.split(/\r?\n/);
      outputBuffer = lines.pop() ?? "";
      for (const line of lines) {
        const port = parseListeningEvent(line);
        if (port) return finish(null, port);
      }
    };
    const onError = (error) => finish(error);
    const onExit = (code) => finish(new Error(`桌面后端意外退出（代码 ${code ?? "未知"}）`));
    child.stdout?.on("data", onData);
    child.once("error", onError);
    child.once("exit", onExit);
  });
}

async function waitForHealth() {
  const deadline = Date.now() + STARTUP_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(backendUrl("/health/live"), {
        headers: { [DESKTOP_HEADER]: backendToken },
        signal: AbortSignal.timeout(2_000),
      });
      if (response.ok) return;
    } catch {
      // FastAPI may still be completing lifespan startup.
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 400));
  }
  throw new Error("桌面后端健康检查超时");
}

function backendEnvironment() {
  const { dataDir, logsDir } = getUserDirectories();
  backendToken = createDesktopToken();
  return {
    ...process.env,
    APP_ENV: "production",
    APP_VERSION: app.getVersion(),
    APP_DATA_DIR: dataDir,
    DATABASE_URL: desktopDatabaseUrl(dataDir),
    DESKTOP_MODE: "true",
    DESKTOP_WEB_DIR: resourcePath("web"),
    DESKTOP_AUTH_TOKEN: backendToken,
    LOG_DIR: logsDir,
    PYTHONDONTWRITEBYTECODE: "1",
    PYTHONIOENCODING: "utf-8",
    USE_CELERY: "false",
  };
}

async function startBackend() {
  const executable = backendExecutablePath();
  if (!existsSync(executable)) {
    throw new Error(`未找到桌面后端：${executable}`);
  }
  const preferredPort = selectPreferredPort();
  const child = spawn(executable, ["--preferred-port", String(preferredPort), "--parent-pid", String(process.pid)], {
    cwd: app.getPath("userData"),
    env: backendEnvironment(),
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  backendProcess = child;
  child.stderr?.on("data", (chunk) => console.error(`[desktop-backend] ${chunk.toString().trim()}`));
  child.on("exit", (code) => {
    const unexpected = !backendExpectedToExit && !isQuitting;
    backendProcess = null;
    backendPort = null;
    if (unexpected && mainWindow && !mainWindow.isDestroyed()) {
      void dialog.showMessageBox(mainWindow, {
        type: "error",
        title: APP_NAME,
        message: "本机服务已停止",
        detail: `知域引擎的本机服务异常退出（代码 ${code ?? "未知"}）。请重新启动应用。`,
      }).then(() => app.quit());
    }
  });
  backendPort = await waitForListeningEvent(child);
  await waitForHealth();
}

function waitForExit(child, timeoutMs) {
  return new Promise((resolvePromise) => {
    if (child.exitCode !== null || child.killed) return resolvePromise();
    const timeout = setTimeout(resolvePromise, timeoutMs);
    child.once("exit", () => {
      clearTimeout(timeout);
      resolvePromise();
    });
  });
}

async function stopBackend() {
  const child = backendProcess;
  backendExpectedToExit = true;
  if (!child) return;
  try {
    await fetch(backendUrl("/api/v1/desktop/shutdown"), {
      method: "POST",
      headers: { [DESKTOP_HEADER]: backendToken },
      signal: AbortSignal.timeout(2_000),
    });
  } catch {
    // A forced process stop below is the last-resort cleanup path.
  }
  await waitForExit(child, SHUTDOWN_TIMEOUT_MS);
  if (child.exitCode === null && !child.killed) child.kill();
  await waitForExit(child, 1_000);
  backendProcess = null;
  backendPort = null;
  backendToken = null;
}

async function boot() {
  configureSession();
  mainWindow = createWindow();
  await startBackend();
  if (mainWindow && !mainWindow.isDestroyed()) await mainWindow.loadURL(backendUrl("/"));
}

const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  });
  app.whenReady().then(boot).catch(async (error) => {
    console.error(error);
    await dialog.showMessageBox({
      type: "error",
      title: APP_NAME,
      message: "应用启动失败",
      detail: error instanceof Error ? error.message : String(error),
    });
    await stopBackend();
    app.exit(1);
  });
  app.on("window-all-closed", () => app.quit());
  app.on("before-quit", (event) => {
    if (isQuitting) return;
    event.preventDefault();
    isQuitting = true;
    void stopBackend().finally(() => app.exit(0));
  });
}
