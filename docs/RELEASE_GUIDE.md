# 知域引擎：GitHub 自动发布

工作流文件是 `.github/workflows/windows-release.yml`。只有推送 `v` 开头的版本标签时才会打包并创建 GitHub Release，普通 `git push` 不会触发安装包构建。

## 第一次上传到 GitHub

1. 登录 GitHub，点击右上角 `+`，选择 **New repository**。
2. 填写仓库名，例如 `zhiyu-engine`。不要勾选自动创建 README、`.gitignore` 或 License，然后点击 **Create repository**。
3. 在项目根目录 PowerShell 依次执行。将下面的地址替换为 GitHub 页面显示的 HTTPS 地址：

```powershell
git status
git add .
git commit -m "feat: add Windows desktop distribution"
git branch -M main
git remote add origin https://github.com/你的GitHub用户名/zhiyu-engine.git
git push -u origin main
```

如果 `git remote add origin` 提示已存在，先执行 `git remote -v` 查看地址；确认要替换时执行：

```powershell
git remote set-url origin https://github.com/你的GitHub用户名/zhiyu-engine.git
```

提交前务必看一遍 `git status`。`.env`、数据库、安装包和用户数据不应出现在待提交列表中。

## 发布第一个安装包

先确认 `package.json` 中的 `version` 是要发布的版本，例如 `1.0.0`，然后执行：

```powershell
git add package.json package-lock.json
git commit -m "chore: release v1.0.0"
git push origin main
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

最后一条命令会自动启动 GitHub Actions。打开仓库顶部 **Actions**，进入 `Build Windows Installer`，等待任务全部显示绿色。随后打开仓库右侧 **Releases**，即可下载 `知域引擎-Setup-1.0.0.exe` 并发给评审或用户。

## 以后每次发新版

1. 修改源码并在本机测试。
2. 将 `package.json` 的 `version` 从旧版本升到新版本，例如 `1.0.1`。
3. 依次执行：

```powershell
git add .
git commit -m "feat: describe this release"
git push origin main
git tag -a v1.0.1 -m "Release v1.0.1"
git push origin v1.0.1
```

4. 等待 Actions 自动生成新安装包和新 Release。

同一个标签不能重复发布。标签推错时，不要直接复用；应把版本加一，例如从 `v1.0.1` 改为 `v1.0.2` 后重新发版。
