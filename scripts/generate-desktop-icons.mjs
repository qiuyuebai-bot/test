#!/usr/bin/env node
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import pngToIco from "png-to-ico";
import sharp from "sharp";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ASSETS_DIR = join(ROOT, "desktop", "assets");
const SOURCE = join(ASSETS_DIR, "icon.svg");
const sizes = [16, 32, 48, 64, 128, 256];

await mkdir(ASSETS_DIR, { recursive: true });
const svg = await readFile(SOURCE);
const pngPaths = [];
for (const size of sizes) {
  const output = join(ASSETS_DIR, `icon-${size}.png`);
  await sharp(svg).resize(size, size).png().toFile(output);
  pngPaths.push(output);
}
await writeFile(join(ASSETS_DIR, "icon.ico"), await pngToIco(pngPaths));
console.log(`桌面图标已生成: ${pngPaths.length} 个 PNG 和 desktop/assets/icon.ico`);
