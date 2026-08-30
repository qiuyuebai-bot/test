#!/usr/bin/env node
import { existsSync } from "node:fs";
import { mkdir, rm } from "node:fs/promises";
import { spawn, spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const BACKEND = join(ROOT, "backend");
const OUTPUT = join(ROOT, "desktop", "out");
const isWindows = process.platform === "win32";
const python = isWindows
  ? join(BACKEND, "venv", "Scripts", "python.exe")
  : join(BACKEND, "venv", "bin", "python");

function run(command, args, options = {}) {
  return new Promise((resolvePromise, rejectPromise) => {
    const child = spawn(command, args, { cwd: ROOT, stdio: "inherit", shell: false, ...options });
    child.on("error", rejectPromise);
    child.on("exit", (code) => {
      code === 0 ? resolvePromise() : rejectPromise(new Error(`${command} 退出，代码 ${code}`));
    });
  });
}

if (!existsSync(python)) {
  throw new Error(`未找到后端构建环境：${python}。请先运行 npm start -- --setup。`);
}
const pyInstallerCheck = spawnSync(python, ["-c", "import PyInstaller"], { stdio: "ignore" });
if (pyInstallerCheck.status !== 0) {
  console.log("首次桌面构建：正在安装 PyInstaller 构建依赖...");
  // requirements files are UTF-8; force Python's UTF-8 mode on Windows locales
  // whose default GBK decoder otherwise fails before pip can parse them.
  await run(python, ["-X", "utf8", "-m", "pip", "install", "-r", join(BACKEND, "requirements-desktop-build.txt")]);
}
await rm(join(OUTPUT, "backend"), { recursive: true, force: true });
await rm(join(OUTPUT, ".pyinstaller"), { recursive: true, force: true });
await mkdir(OUTPUT, { recursive: true });
await run(python, [
  "-m", "PyInstaller",
  "--noconfirm",
  "--clean",
  "--distpath", OUTPUT,
  "--workpath", join(OUTPUT, ".pyinstaller"),
  join(ROOT, "desktop", "backend.spec"),
]);

const executable = join(OUTPUT, "backend", isWindows ? "zhiyu-backend.exe" : "zhiyu-backend");
if (!existsSync(executable)) throw new Error(`PyInstaller 未产出预期后端：${executable}`);
console.log(`桌面后端已生成: ${executable}`);
