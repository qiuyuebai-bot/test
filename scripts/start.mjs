#!/usr/bin/env node
/**
 * 一键启动脚本（跨平台）
 *
 * 功能：
 *   1. 自动检测前后端项目目录结构
 *   2. 检测运行环境（Node / Python / venv / node_modules / .env）
 *   3. 支持通过 --setup 参数自动准备环境
 *   4. 并行启动前端开发服务器和后端服务
 *   5. 实时聚合输出，带 [backend] / [frontend] 前缀着色
 *   6. Ctrl+C 优雅关闭两个子进程
 *
 * 用法：
 *   node scripts/start.mjs            # 启动前后端
 *   node scripts/start.mjs --setup   # 自动准备环境（创建 venv、安装依赖、复制 .env）
 *   node scripts/start.mjs --backend # 仅启动后端
 *   node scripts/start.mjs --frontend # 仅启动前端
 */

import { spawn, spawnSync } from "node:child_process";
import { existsSync, copyFileSync, mkdirSync } from "node:fs";
import { createServer } from "node:net";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { createInterface } from "node:readline";

// ============================================================
// 配置（集中管理，便于后续扩展）
// ============================================================
const CONFIG = {
  backend: {
    dir: "backend",
    venvDirs: ["venv", ".venv"],
    entryModule: "app.main:app",
    host: "0.0.0.0",
    port: 8000,
    healthPath: "/api/v1/health/live",
    startupTimeoutMs: 60000,
    requirementsFile: "requirements.txt",
  },
  frontend: {
    dir: ".",
    packageJson: "package.json",
    devScript: "serve",
    nodeModules: "node_modules",
    port: 5173,
    startupTimeoutMs: 120000,
    titleMarker: "<title>领域知识个性化生成与多智能体协同决策系统</title>",
  },
  envExample: ".env.example",
  envFile: ".env",
  colors: {
    backend: "\x1b[36m",   // cyan
    frontend: "\x1b[35m",  // magenta
    info: "\x1b[34m",      // blue
    success: "\x1b[32m",   // green
    warn: "\x1b[33m",     // yellow
    error: "\x1b[31m",    // red
    dim: "\x1b[2m",       // dim
    reset: "\x1b[0m",
  },
};

// ============================================================
// 工具函数
// ============================================================
const ROOT = process.cwd();
const IS_WINDOWS = process.platform === "win32";
const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));

function log(level, msg) {
  const c = CONFIG.colors[level] || "";
  const r = CONFIG.colors.reset;
  const prefix = {
    info: "ℹ",
    success: "✓",
    warn: "⚠",
    error: "✗",
  }[level] || "•";
  console.log(`${c}${prefix}${r} ${msg}`);
}

function section(title) {
  const c = CONFIG.colors.info;
  const r = CONFIG.colors.reset;
  console.log(`\n${c}── ${title} ──${r}`);
}

function findVenv(backendDir) {
  for (const v of CONFIG.backend.venvDirs) {
    const venvPath = join(backendDir, v);
    const pythonExe = IS_WINDOWS
      ? join(venvPath, "Scripts", "python.exe")
      : join(venvPath, "bin", "python");
    if (existsSync(pythonExe)) {
      const check = spawnSync(pythonExe, ["--version"], {
        encoding: "utf8",
        shell: false,
      });
      if (check.status === 0) return { venvPath, pythonExe };
    }
  }
  return null;
}

function findPython() {
  // 优先使用系统 python，回退到 python3
  for (const cmd of ["python", "python3"]) {
    try {
      const result = spawnSync(cmd, ["--version"], {
        shell: IS_WINDOWS,
        encoding: "utf8",
      });
      if (result.status === 0) return cmd;
    } catch {
      // continue
    }
  }
  return null;
}

function findNpm() {
  // Windows 下优先用 npm.cmd（避免 PowerShell ExecutionPolicy 限制）
  return IS_WINDOWS ? "npm.cmd" : "npm";
}

// ============================================================
// 环境检测
// ============================================================
function detectEnvironment() {
  section("环境检测");
  const backendDir = join(ROOT, CONFIG.backend.dir);
  const frontendDir = join(ROOT, CONFIG.frontend.dir);
  const frontendPkg = join(frontendDir, CONFIG.frontend.packageJson);

  const result = {
    backendDir,
    backendExists: existsSync(backendDir),
    backendMainExists: existsSync(join(backendDir, "app", "main.py")),
    requirementsExists: existsSync(join(backendDir, CONFIG.backend.requirementsFile)),
    venv: findVenv(backendDir),
    python: findPython(),

    frontendDir,
    frontendPkgExists: existsSync(frontendPkg),
    nodeModulesExists: existsSync(join(frontendDir, CONFIG.frontend.nodeModules)),

    envExists: existsSync(join(ROOT, CONFIG.envFile)),
    envExampleExists: existsSync(join(ROOT, CONFIG.envExample)),
  };

  // 输出检测结果
  const check = (label, ok, hint) => {
    const mark = ok ? `${CONFIG.colors.success}✓${CONFIG.colors.reset}` : `${CONFIG.colors.error}✗${CONFIG.colors.reset}`;
    const suffix = ok ? "" : (hint ? `  ${CONFIG.colors.dim}(${hint})${CONFIG.colors.reset}` : "");
    console.log(`  ${mark} ${label}${suffix}`);
  };

  check("后端目录 backend/", result.backendExists);
  check("后端入口 app/main.py", result.backendMainExists);
  check("后端依赖 requirements.txt", result.requirementsExists);
  check("Python 虚拟环境", !!result.venv, result.python ? "未创建，运行 --setup 自动创建" : "未安装 Python");
  check("前端 package.json", result.frontendPkgExists);
  check("前端 node_modules/", result.nodeModulesExists, "未安装，运行 --setup 自动安装");
  check(".env 配置文件", result.envExists, "未创建，运行 --setup 自动复制");

  return result;
}

// ============================================================
// 环境准备（--setup）
// ============================================================
function runSetup(env) {
  section("环境准备");

  // 1. .env 文件
  if (!env.envExists && env.envExampleExists) {
    try {
      copyFileSync(join(ROOT, CONFIG.envExample), join(ROOT, CONFIG.envFile));
      log("success", "已从 .env.example 创建 .env");
    } catch (e) {
      log("error", `创建 .env 失败: ${e.message}`);
    }
  } else if (env.envExists) {
    log("info", ".env 已存在，跳过");
  } else {
    log("warn", "未找到 .env.example，请手动创建 .env");
  }

  // 2. 后端 venv
  if (!env.venv) {
    if (!env.python) {
      log("error", "未检测到 Python，请先安装 Python 3.11+");
      return false;
    }
    const venvName = CONFIG.backend.venvDirs[0];
    const venvPath = join(env.backendDir, venvName);
    log("info", `创建虚拟环境: ${venvPath}`);
    const r1 = spawnSync(env.python, ["-m", "venv", venvName], {
      cwd: env.backendDir,
      stdio: "inherit",
      shell: IS_WINDOWS,
    });
    if (r1.status !== 0) {
      log("error", "创建虚拟环境失败");
      return false;
    }
    const pythonExe = IS_WINDOWS
      ? join(venvPath, "Scripts", "python.exe")
      : join(venvPath, "bin", "python");
    log("info", "安装后端依赖（可能耗时数分钟）...");
    const r2 = spawnSync(pythonExe, ["-m", "pip", "install", "-r", CONFIG.backend.requirementsFile], {
      cwd: env.backendDir,
      stdio: "inherit",
      shell: IS_WINDOWS,
    });
    if (r2.status !== 0) {
      log("error", "安装后端依赖失败");
      return false;
    }
    env.venv = { venvPath, pythonExe };
    log("success", "后端环境就绪");
  } else {
    log("info", "虚拟环境已存在，跳过创建");
  }

  // 3. 前端依赖
  if (!env.nodeModulesExists) {
    log("info", "安装前端依赖（可能耗时数分钟）...");
    const npm = findNpm();
    const r = spawnSync(npm, ["install"], {
      cwd: env.frontendDir,
      stdio: "inherit",
      shell: IS_WINDOWS,
    });
    if (r.status !== 0) {
      log("error", "安装前端依赖失败");
      return false;
    }
    log("success", "前端依赖就绪");
  } else {
    log("info", "node_modules 已存在，跳过安装");
  }

  log("success", "环境准备完成");
  return true;
}

// ============================================================
// 启动服务
// ============================================================
function startBackend(env) {
  const { pythonExe } = env.venv;
  const args = [
    "-m", "uvicorn",
    CONFIG.backend.entryModule,
    "--reload",
    "--host", CONFIG.backend.host,
    "--port", String(CONFIG.backend.port),
  ];

  log("info", `启动后端: ${pythonExe} ${args.join(" ")}`);
  const proc = spawn(pythonExe, args, {
    cwd: env.backendDir,
    shell: false,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  });

  return { proc, label: "backend", color: CONFIG.colors.backend };
}

function startFrontend(env) {
  const npm = findNpm();
  const args = ["run", CONFIG.frontend.devScript];

  log("info", `启动前端: ${npm} ${args.join(" ")}`);
  const proc = spawn(npm, args, {
    cwd: env.frontendDir,
    shell: IS_WINDOWS, // Windows 下需要 shell 调用 npm.cmd
    env: { ...process.env, FORCE_COLOR: "1" },
  });

  return { proc, label: "frontend", color: CONFIG.colors.frontend };
}

async function waitForHttpReady(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2000);
    try {
      const response = await fetch(url, { signal: controller.signal });
      if (response.ok) return true;
    } catch {
      // The service may still be initializing.
    } finally {
      clearTimeout(timeoutId);
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

function isPortAvailable(port) {
  return new Promise((resolve) => {
    const server = createServer();
    server.unref();
    server.once("error", () => resolve(false));
    server.listen({ host: "0.0.0.0", port, exclusive: true }, () => {
      server.close(() => resolve(true));
    });
  });
}

async function isExpectedServiceRunning(url, validate) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 2000);
  try {
    const response = await fetch(url, { signal: controller.signal });
    if (!response.ok) return false;
    return validate(await response.text());
  } catch {
    return false;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function inspectServicePort({ label, port, url, validate }) {
  if (await isPortAvailable(port)) return { reuse: false, conflict: false };

  if (await isExpectedServiceRunning(url, validate)) {
    log("warn", `${label}端口 ${port} 已有本项目服务运行，将直接复用`);
    return { reuse: true, conflict: false };
  }

  log("error", `${label}端口 ${port} 已被其他程序占用，请关闭占用进程后重试`);
  return { reuse: false, conflict: true };
}

function openFrontend() {
  const url = `http://localhost:${CONFIG.frontend.port}/`;
  const command = IS_WINDOWS
    ? { file: "cmd.exe", args: ["/d", "/s", "/c", "start", "", url] }
    : process.platform === "darwin"
      ? { file: "open", args: [url] }
      : { file: "xdg-open", args: [url] };

  try {
    const opener = spawn(command.file, command.args, {
      detached: true,
      stdio: "ignore",
      windowsHide: true,
    });
    opener.unref();
    log("success", `服务已就绪，正在打开: ${url}`);
  } catch (error) {
    log("warn", `无法自动打开浏览器，请手动访问 ${url}（${error.message}）`);
  }
}

// ============================================================
// 进程管理：输出聚合 + 优雅关闭
// ============================================================
function attachOutput(service) {
  const { proc, label, color } = service;
  const reset = CONFIG.colors.reset;

  const prefixLine = (line) => {
    const text = line.toString().replace(/\r?\n$/, "");
    if (text) process.stdout.write(`${color}[${label}]${reset} ${text}\n`);
  };

  if (proc.stdout) {
    proc.stdout.on("data", prefixLine);
  }
  if (proc.stderr) {
    proc.stderr.on("data", prefixLine);
  }
  proc.on("error", (err) => {
    if (service.stopping) return;
    log("error", `[${label}] 启动失败: ${err.message}`);
  });
  proc.on("exit", (code, signal) => {
    if (service.stopping) return;
    if (signal === "SIGTERM" || signal === "SIGINT") return;
    service.onUnexpectedExit?.();
    if (code === 0) {
      log("info", `[${label}] 进程退出 (code=0)`);
    } else {
      log("error", `[${label}] 进程异常退出 (code=${code})`);
    }
  });
}

// ============================================================
// 主入口
// ============================================================
function printUsage() {
  console.log(`
用法:
  node scripts/start.mjs [options]

选项:
  --setup        自动准备环境（创建 venv、安装依赖、复制 .env）
  --backend      仅启动后端
  --frontend     仅启动前端
  --help, -h     显示帮助
`);
}

async function main() {
  const argv = process.argv.slice(2);
  const flags = {
    setup: argv.includes("--setup"),
    onlyBackend: argv.includes("--backend"),
    onlyFrontend: argv.includes("--frontend"),
    help: argv.includes("--help") || argv.includes("-h"),
  };

  if (flags.help) {
    printUsage();
    process.exit(0);
  }

  const banner = `${CONFIG.colors.info}
╔════════════════════════════════════════════════════════════╗
║          一键启动 · 前后端并行服务                          ║
║          Backend: FastAPI + Uvicorn                        ║
║          Frontend: Vite + React                           ║
╚════════════════════════════════════════════════════════════╝${CONFIG.colors.reset}`;
  console.log(banner);

  const env = detectEnvironment();

  // 关键缺失项校验
  const criticalIssues = [];
  if (!env.backendExists) criticalIssues.push("后端目录 backend/ 不存在");
  if (!env.frontendPkgExists) criticalIssues.push("前端 package.json 不存在");
  if (criticalIssues.length) {
    section("错误");
    criticalIssues.forEach((m) => log("error", m));
    process.exit(1);
  }

  // --setup 模式
  if (flags.setup) {
    const ok = runSetup(env);
    if (!ok) process.exit(1);
    process.exit(0);
  }

  // 启动前的就绪检查
  const wantBackend = !flags.onlyFrontend;
  const wantFrontend = !flags.onlyBackend;

  const notReady = [];
  if (wantBackend && !env.venv) {
    notReady.push("后端虚拟环境未创建（运行: node scripts/start.mjs --setup）");
  }
  if (wantFrontend && !env.nodeModulesExists) {
    notReady.push("前端依赖未安装（运行: node scripts/start.mjs --setup）");
  }
  if (notReady.length) {
    section("启动前检查未通过");
    notReady.forEach((m) => log("warn", m));
    log("info", "提示: 先执行 `node scripts/start.mjs --setup` 准备环境");
    process.exit(1);
  }

  // 先识别已运行的本项目服务，避免 Vite 因严格端口冲突退出并连带关闭后端。
  const backendState = wantBackend
    ? await inspectServicePort({
        label: "后端",
        port: CONFIG.backend.port,
        url: `http://127.0.0.1:${CONFIG.backend.port}${CONFIG.backend.healthPath}`,
        validate: (body) => body.includes('"status":"alive"'),
      })
    : { reuse: false, conflict: false };
  const frontendState = wantFrontend
    ? await inspectServicePort({
        label: "前端",
        port: CONFIG.frontend.port,
        url: `http://127.0.0.1:${CONFIG.frontend.port}/`,
        validate: (body) => body.includes(CONFIG.frontend.titleMarker),
      })
    : { reuse: false, conflict: false };

  if (backendState.conflict || frontendState.conflict) {
    log("info", "未启动任何新服务，已有进程不会被关闭");
    process.exit(1);
  }

  // 启动服务
  const services = [];
  if (wantBackend && !backendState.reuse) services.push(startBackend(env));
  if (wantFrontend && !frontendState.reuse) services.push(startFrontend(env));

  services.forEach(attachOutput);

  section("服务地址");
  if (wantBackend) {
    log("info", `${backendState.reuse ? "后端已运行" : "后端启动中"}:  http://localhost:${CONFIG.backend.port}`);
    log("info", `API 文档:  http://localhost:${CONFIG.backend.port}/docs`);
  }
  if (wantFrontend) {
    if (frontendState.reuse) {
      log("info", `前端已运行:  http://localhost:${CONFIG.frontend.port}`);
    } else {
      log("info", `前端正在构建；看到 Vite 输出 Local 地址后再打开:  http://localhost:${CONFIG.frontend.port}`);
    }
  }
  if (services.length === 0) {
    log("success", "前后端均已运行，无需重复启动");
    if (wantFrontend) openFrontend();
    return;
  }
  console.log(`\n${CONFIG.colors.dim}按 Ctrl+C 停止本次启动的服务${CONFIG.colors.reset}\n`);

  // 优雅关闭
  let shuttingDown = false;
  const shutdown = (signal) => {
    if (shuttingDown) return;
    shuttingDown = true;
    console.log(`\n${CONFIG.colors.warn}收到 ${signal}，正在关闭服务...${CONFIG.colors.reset}`);
    services.forEach((s) => {
      try {
        s.stopping = true;
        if (s.proc.killed) return;
        if (IS_WINDOWS) {
          spawnSync("taskkill", ["/pid", String(s.proc.pid), "/t", "/f"], {
            stdio: "ignore",
            windowsHide: true,
          });
        } else {
          s.proc.kill("SIGTERM");
        }
      } catch (e) {
        log("error", `[${s.label}] 关闭失败: ${e.message}`);
      }
    });
    setTimeout(() => {
      log("info", "已停止所有服务");
      process.exit(0);
    }, 800);
  };

  services.forEach((service) => {
    service.onUnexpectedExit = () => shutdown(`${service.label} exit`);
  });

  const healthUrl = `http://127.0.0.1:${CONFIG.backend.port}${CONFIG.backend.healthPath}`;
  const frontendUrl = `http://127.0.0.1:${CONFIG.frontend.port}/`;
  void Promise.all([
    wantBackend ? waitForHttpReady(healthUrl, CONFIG.backend.startupTimeoutMs) : true,
    wantFrontend ? waitForHttpReady(frontendUrl, CONFIG.frontend.startupTimeoutMs) : true,
  ]).then(([backendReady, frontendReady]) => {
    if (!backendReady) {
      log("error", `后端健康检查超时: ${healthUrl}`);
      shutdown("backend readiness timeout");
      return;
    }
    if (!frontendReady) {
      log("error", `前端启动检查超时: ${frontendUrl}`);
      shutdown("frontend readiness timeout");
      return;
    }

    if (wantBackend) log("success", `后端健康检查通过: ${healthUrl}`);
    if (wantFrontend) openFrontend();
  });

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));

  // Windows 下 Ctrl+C 处理
  if (IS_WINDOWS) {
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    rl.on("SIGINT", () => shutdown("SIGINT"));
  }
}

main().catch((error) => {
  log("error", `启动检查失败: ${error.message}`);
  process.exit(1);
});
