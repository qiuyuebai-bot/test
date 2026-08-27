# 知域引擎：首次生成 Windows 安装包

这份指南只在开发电脑上执行一次。生成的安装包可以直接发给其他 Windows 用户；他们不需要安装 Node.js、Python、Git、Redis 或 ChromaDB。

## 需要准备

1. 安装 Node.js 22 LTS 和 Python 3.12（只需要开发者电脑安装）。安装后重新打开 PowerShell。
2. 打开项目根目录 `C:\Users\fhb\Downloads\test\test`。
3. 第一次执行以下两条命令：

```powershell
npm ci
npm start -- --setup
```

第二条命令只做环境准备，看到“环境准备完成”后按 Ctrl+C 或等待它结束即可。它不会删除你的源码、数据库或 AI 配置。

## 生成安装包

执行：

```powershell
npm run build:electron
```

这个命令依次完成前端生产构建、图标生成、后端独立打包、后端登录冒烟测试和 Windows NSIS 安装程序生成。第一次通常较久，因为需要打包现有的模型和向量库依赖。

成功后文件在：

```text
release\知域引擎-Setup-1.0.0.exe
```

版本号来自根目录 `package.json` 的 `version`。要发布新版本，先将它从 `1.0.0` 改为例如 `1.0.1`，再执行同一条构建命令。

## 本机体验

1. 双击 `release\知域引擎-Setup-<版本号>.exe`。
2. 完成安装后从桌面打开“知域引擎”。
3. 首次启动自行设置本机管理员账号和密码。
4. 登录后可按引导配置 AI 服务，也可暂不配置进入演示模式。

安装包和 `release/` 都已被 Git 忽略，不会被提交到代码仓库。

## 常见情况

- `未找到后端构建环境`：先执行 `npm start -- --setup`。
- 构建很慢：正常。完整包会携带现有的 Python、模型、向量和数据分析依赖；不要中途关闭 PowerShell。
- Windows 提示“未知发布者”：这是未购买代码签名证书时的正常提示。正式公开分发前应配置企业代码签名证书。
