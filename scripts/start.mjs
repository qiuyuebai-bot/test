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
    requirementsFile: "requirements.txt",
  },
  frontend: {
    dir: ".",
    packageJson: "package.json",
    devScript: "dev",
    nodeModules: "node_modules",
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
      return { venvPath, pythonExe };
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
    log("error", `[${label}] 启动失败: ${err.message}`);
  });
  proc.on("exit", (code, signal) => {
    if (signal === "SIGTERM" || signal === "SIGINT") return;
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

function main() {
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

  // 启动服务
  const services = [];
  if (wantBackend) services.push(startBackend(env));
  if (wantFrontend) services.push(startFrontend(env));

  services.forEach(attachOutput);

  section("服务地址");
  if (wantBackend) {
    log("success", `后端 API:  http://localhost:${CONFIG.backend.port}`);
    log("info", `API 文档:  http://localhost:${CONFIG.backend.port}/docs`);
  }
  if (wantFrontend) {
    log("success", "前端页面:  http://localhost:5173");
  }
  console.log(`\n${CONFIG.colors.dim}按 Ctrl+C 停止所有服务${CONFIG.colors.reset}\n`);

  // 优雅关闭
  let shuttingDown = false;
  const shutdown = (signal) => {
    if (shuttingDown) return;
    shuttingDown = true;
    console.log(`\n${CONFIG.colors.warn}收到 ${signal}，正在关闭服务...${CONFIG.colors.reset}`);
    services.forEach((s) => {
      try {
        if (!s.proc.killed) s.proc.kill("SIGTERM");
      } catch (e) {
        log("error", `[${s.label}] 关闭失败: ${e.message}`);
      }
    });
    setTimeout(() => {
      log("info", "已停止所有服务");
      process.exit(0);
    }, 800);
  };

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));

  // Windows 下 Ctrl+C 处理
  if (IS_WINDOWS) {
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    rl.on("SIGINT", () => shutdown("SIGINT"));
  }
}

main();
