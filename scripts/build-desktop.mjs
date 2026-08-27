#!/usr/bin/env node
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { readFile, writeFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const isWindows = process.platform === "win32";
const unpacked = process.argv.includes("--dir");
const packageOnly = process.argv.includes("--package-only");
const npm = isWindows ? "npm.cmd" : "npm";
const builder = isWindows
  ? join(ROOT, "node_modules", ".bin", "electron-builder.cmd")
  : join(ROOT, "node_modules", ".bin", "electron-builder");
const electronExecutable = join(
  ROOT,
  "node_modules",
  "electron",
  "dist",
  isWindows ? "electron.exe" : process.platform === "darwin" ? "Electron.app" : "electron",
);
const electronInstaller = join(ROOT, "node_modules", "electron", "install.js");

function run(command, args) {
  return new Promise((resolvePromise, rejectPromise) => {
    // Windows 的 npm 与 electron-builder 是 .cmd 文件，需经 cmd.exe 启动。
    const shell = isWindows && command.toLowerCase().endsWith(".cmd");
    const child = spawn(command, args, { cwd: ROOT, stdio: "inherit", shell });
    child.on("error", rejectPromise);
    child.on("exit", (code) => {
      code === 0 ? resolvePromise() : rejectPromise(new Error(`${command} 退出，代码 ${code}`));
    });
  });
}

if (!packageOnly) {
  await run(npm, ["run", "build"]);
  await run(npm, ["run", "desktop:icons"]);
  await run(npm, ["run", "desktop:backend"]);
  await run(process.execPath, [join(ROOT, "scripts", "desktop-smoke.mjs")]);
}

// 受限环境可能跳过 Electron 的 postinstall，此处在打包前补齐本机运行时。
if (!existsSync(electronExecutable)) {
  if (!existsSync(electronInstaller)) {
    throw new Error("未找到 Electron 安装脚本，请先执行 npm install。");
  }
  await run(process.execPath, [electronInstaller]);
}

await run(builder, ["--config", join(ROOT, "desktop", "electron-builder.yml"), "--win", ...(unpacked ? ["--dir"] : [])]);

if (!unpacked) {
  const installer = join(ROOT, "release", `知域引擎-Setup-${JSON.parse(await readFile(join(ROOT, "package.json"), "utf8")).version}.exe`);
  if (!existsSync(installer)) throw new Error(`未找到安装包：${installer}`);
  const digest = createHash("sha256").update(await readFile(installer)).digest("hex");
  const checksumFile = `${installer}.sha256`;
  await writeFile(checksumFile, `${digest}  ${basename(installer)}\n`, "utf8");
  console.log(`安装包已生成：${installer}`);
  console.log(`SHA-256：${digest}`);
  console.log(`校验文件已生成：${checksumFile}`);
}
