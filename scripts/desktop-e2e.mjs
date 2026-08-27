#!/usr/bin/env node
import { existsSync } from "node:fs";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { _electron as electron } from "playwright";

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const outputDirectory = process.env.DESKTOP_E2E_OUTPUT_DIR || "release-staging";
const executable = join(ROOT, outputDirectory, "win-unpacked", "知域引擎.exe");

if (process.platform !== "win32") throw new Error("桌面端端到端测试仅支持 Windows。");
if (!existsSync(executable)) throw new Error(`未找到已构建程序：${executable}`);

const appData = await mkdtemp(join(tmpdir(), "zhiyu-electron-e2e-"));
let application;
let page;

try {
  application = await electron.launch({
    executablePath: executable,
    env: { ...process.env, ZHIYU_USER_DATA_DIR: appData },
  });
  page = await application.firstWindow();
  await page.getByRole("heading", { name: "创建本机管理员" }).waitFor();
  await page.locator("#desktop-admin-username").fill("desktop_admin");
  await page.locator("#desktop-admin-password").fill("Desktop123");
  await page.locator("#desktop-admin-confirm-password").fill("Desktop123");
  await page.getByRole("button", { name: "创建并进入工作台" }).click();

  await page.getByRole("heading", { name: "连接 AI 服务" }).waitFor();
  await page.getByRole("button", { name: "稍后配置" }).click();
  await page.waitForURL(/\/dashboard$/);

  await page.evaluate(() => {
    localStorage.clear();
    window.location.assign("/login");
  });
  await page.getByRole("heading", { name: "登录账号" }).waitFor();
  await page.getByPlaceholder("请输入用户名").fill("desktop_admin");
  await page.getByPlaceholder("请输入密码").fill("Desktop123");
  await page.locator("form").getByRole("button", { name: "登录", exact: true }).click();
  await page.waitForURL(/\/dashboard$/);

  console.log("桌面端端到端测试通过：首次初始化、AI 配置跳过与真实登录均正常。");
} catch (error) {
  if (page) {
    console.error(`桌面窗口地址：${page.url()}`);
    console.error(`页面内容：${(await page.locator("body").innerText()).slice(0, 1_000)}`);
    await page.screenshot({ path: join(ROOT, "desktop", "out", "desktop-e2e-failure.png") });
  }
  throw error;
} finally {
  await application?.close();
  await rm(appData, { recursive: true, force: true });
}
