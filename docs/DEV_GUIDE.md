# 知域引擎：开发协作说明

桌面安装包只给最终用户使用。开发者修改源码时继续使用原有前后端开发模式，不需要先安装桌面包。

## 拉取并运行

```powershell
git pull
npm ci
npm start -- --setup
npm start
```

最后一条命令会启动 Vite 前端和 FastAPI 后端，并自动打开浏览器。开发地址通常为 `http://localhost:5173`。

## 提交前检查

```powershell
npm run typecheck
npm test
cd backend
venv\Scripts\python.exe -m pytest
cd ..
```

桌面相关修改还应执行：

```powershell
node --test desktop/main.test.mjs
npm run build:electron
```

不要提交 `.env`、数据库、`data/` 用户数据、`dist/`、`desktop/out/`、`release/` 或 `.exe`。这些路径已在 `.gitignore` 中排除。
