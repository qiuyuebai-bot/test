#!/usr/bin/env node
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { DESKTOP_HEADER, parseListeningEvent, selectPreferredPort } from "../desktop/runtime.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const executable = process.argv[2] || join(ROOT, "desktop", "out", "backend", "zhiyu-backend.exe");
const token = "desktop-smoke-token-for-local-package";

if (!existsSync(executable)) throw new Error(`未找到待测桌面后端：${executable}`);

// AI 连通性测试不依赖模板。确认模板被装入冻结包，避免业务生成在安装后才失败。
const bundledPrompts = join(dirname(executable), "_internal", "app", "prompts");
for (const file of ["manifest.json", "templates/question_generation.txt", "templates/resource_generation.txt"]) {
  assert.ok(existsSync(join(bundledPrompts, file)), `桌面包缺少 AI 提示词资源：${file}`);
}

function readListeningPort(child) {
  return new Promise((resolvePromise, rejectPromise) => {
    let text = "";
    const timeout = setTimeout(() => rejectPromise(new Error(`未收到桌面后端就绪事件：${text.slice(-1500)}`)), 60_000);
    const done = (error, port) => {
      clearTimeout(timeout);
      child.stdout?.off("data", onData);
      child.once("error", () => {});
      error ? rejectPromise(error) : resolvePromise(port);
    };
    const onData = (chunk) => {
      text += chunk.toString();
      const lines = text.split(/\r?\n/);
      text = lines.pop() ?? "";
      for (const line of lines) {
        const port = parseListeningEvent(line);
        if (port) return done(null, port);
      }
    };
    child.stdout?.on("data", onData);
    child.once("error", (error) => done(error));
    child.once("exit", (code) => done(new Error(`桌面后端提前退出：${code ?? "未知"}`)));
  });
}

async function request(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: { [DESKTOP_HEADER]: token, ...(options.headers || {}) },
    signal: AbortSignal.timeout(15_000),
  });
  const contentType = response.headers.get("content-type") || "";
  return {
    response,
    data: contentType.includes("application/json") ? await response.json() : await response.text(),
  };
}

async function waitForHealthyBackend(baseUrl, getDiagnostics) {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/health/live`, {
        headers: { [DESKTOP_HEADER]: token },
        signal: AbortSignal.timeout(2_000),
      });
      if (response.ok) return;
    } catch {
      // 端口已绑定但 FastAPI 生命周期初始化尚未完成时继续等待。
    }
    await new Promise((resolvePromise) => setTimeout(resolvePromise, 400));
  }
  throw new Error(`桌面后端健康检查超时。后端输出：${getDiagnostics().slice(-2_000)}`);
}

async function waitForExit(child) {
  return new Promise((resolvePromise) => {
    if (child.exitCode !== null) return resolvePromise();
    const timeout = setTimeout(resolvePromise, 10_000);
    child.once("exit", () => {
      clearTimeout(timeout);
      resolvePromise();
    });
  });
}

async function removeWorkspace(workspace) {
  let lastError;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    try {
      await rm(workspace, { recursive: true, force: true, maxRetries: 1, retryDelay: 300 });
      return;
    } catch (error) {
      lastError = error;
      if (error?.code !== "EBUSY" && error?.code !== "ENOTEMPTY") throw error;
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 500));
    }
  }
  throw lastError;
}

const workspace = await mkdtemp(join(tmpdir(), "zhiyu-desktop-smoke-"));
const dataDir = join(workspace, "data");
const webDir = join(workspace, "web");
await mkdir(webDir, { recursive: true });
await writeFile(join(webDir, "index.html"), "<!doctype html><title>知域引擎测试</title><div id=\"root\"></div>", "utf8");
let child = null;
let passed = false;

try {
  child = spawn(executable, ["--preferred-port", String(selectPreferredPort()), "--parent-pid", String(process.pid)], {
    cwd: workspace,
    env: {
      ...process.env,
      APP_DATA_DIR: dataDir,
      APP_ENV: "production",
      DATABASE_URL: `sqlite:///${join(dataDir, "app.db").replace(/\\/g, "/")}`,
      DESKTOP_AUTH_TOKEN: token,
      DESKTOP_MODE: "true",
      DESKTOP_WEB_DIR: webDir,
      PYTHONDONTWRITEBYTECODE: "1",
      USE_CELERY: "false",
    },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  let stderr = "";
  child.stderr?.on("data", (chunk) => { stderr += chunk.toString(); });
  const port = await readListeningPort(child);
  const baseUrl = `http://127.0.0.1:${port}`;
  await waitForHealthyBackend(baseUrl, () => stderr);

  const noHeader = await fetch(`${baseUrl}/health/live`, { signal: AbortSignal.timeout(15_000) });
  assert.equal(noHeader.status, 403, "没有 Electron 会话令牌时必须被拒绝");
  assert.equal((await request(`${baseUrl}/health/live`)).response.status, 200);

  const status = await request(`${baseUrl}/api/v1/desktop/bootstrap-status`);
  assert.equal(status.response.status, 200);
  assert.equal(status.data.data.required, true);

  const bootstrap = await request(`${baseUrl}/api/v1/desktop/bootstrap`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "desktop_admin", password: "SmokePass2026" }),
  });
  assert.equal(bootstrap.response.status, 201, JSON.stringify(bootstrap.data));
  assert.ok(bootstrap.data.data.access_token, "首次初始化必须签发登录令牌");

  const login = await request(`${baseUrl}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "desktop_admin", password: "SmokePass2026" }),
  });
  assert.equal(login.response.status, 200, JSON.stringify(login.data));
  assert.ok(login.data.data.access_token, "真实登录必须成功");

  const spa = await request(`${baseUrl}/dashboard`);
  assert.equal(spa.response.status, 200);
  assert.match(spa.data, /id="root"/);

  const shutdown = await request(`${baseUrl}/api/v1/desktop/shutdown`, { method: "POST" });
  assert.equal(shutdown.response.status, 200);
  await waitForExit(child);
  if (child.exitCode === null) throw new Error(`桌面后端未在关闭请求后退出。日志：${stderr.slice(-1500)}`);
  passed = true;
  console.log("桌面后端冒烟测试通过：会话保护、首次初始化、真实登录、SPA 静态页和优雅退出均正常。");
} finally {
  if (child?.exitCode === null) {
    child.kill();
    await waitForExit(child);
  }
  if (passed) {
    await removeWorkspace(workspace);
  } else {
    console.error(`桌面冒烟测试失败，已保留诊断目录：${workspace}`);
  }
}
