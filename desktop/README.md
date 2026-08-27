# 知域引擎桌面发行目录

此目录只包含 Windows 桌面版的运行外壳、安装器配置和品牌资源。

- `main.mjs`：Electron 主进程，管理单实例窗口和后端生命周期。
- `preload.cjs`：受限的渲染进程桥接，不暴露文件系统或任意 IPC。
- `backend.spec`：PyInstaller 后端构建配置。
- `assets/`：可追踪的图标源文件与安装说明；生成的 ICO、PNG 不提交。
- `out/`：PyInstaller 中间产物，不提交。

日常 Web 开发仍使用 `npm start`。生成 Windows 安装包使用 `npm run build:electron`。
