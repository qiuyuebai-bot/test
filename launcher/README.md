# 项目一键启动器

这是一个轻量 Windows 启动器。它不打包 Node.js、Python 或项目依赖，而是复用项目根目录中的 `scripts/start.mjs`。

## 使用条件

- Windows x64（也可用 `win-arm64` 参数构建）
- Node.js 18+
- 项目根目录已完成 `node_modules` 和 `backend/venv` 初始化
- .NET 8 SDK（仅构建时需要）

## 构建

在项目根目录执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\launcher\build.ps1
```

生成文件位于 `launcher/publish/ProjectLauncher.exe`。将 EXE 放到项目根目录，双击即可启动。

如果目标机器是 ARM64：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\launcher\build.ps1 -Runtime win-arm64
```

## 行为

- 自动查找项目根目录并检查 Node.js、虚拟环境、`node_modules` 和必要文件。
- 启动现有 `scripts/start.mjs`，聚合显示前后端日志。
- 等待 `http://127.0.0.1:8000/health/live` 和 `http://127.0.0.1:5173/` 就绪后打开浏览器。
- 关闭窗口或点击“停止服务”时结束启动脚本及其子进程。
- 使用本地互斥锁避免重复启动多个启动器。
