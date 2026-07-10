@echo off
chcp 65001 >nul
title 领域知识多智能体系统 - Docker 一键启动

echo.
echo  ╔═══════════════════════════════════════════════════════════╗
echo  ║     领域知识个性化生成与多智能体协同决策系统               ║
echo  ║     Docker 一键部署                                        ║
echo  ╚═══════════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM ---- 检测 Docker ----
where docker >nul 2>nul
if errorlevel 1 (
    echo  [X] 未检测到 Docker，请先安装 Docker Desktop
    echo      下载地址: https://www.docker.com/products/docker-desktop/
    echo.
    pause
    exit /b 1
)
echo  [OK] 已检测到 Docker

REM ---- 检测 Docker 引擎运行状态 ----
docker info >nul 2>nul
if errorlevel 1 (
    echo  [X] Docker 引擎未运行，请启动 Docker Desktop 后重试
    echo      等待 Docker Desktop 图标变为绿色后，再次双击此脚本
    echo.
    pause
    exit /b 1
)
echo  [OK] Docker 引擎运行中

REM ---- 创建 .env（如不存在）----
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo  [OK] 已从 .env.example 创建 .env 配置文件
    ) else (
        echo  [!]  未找到 .env.example，将使用默认配置
    )
) else (
    echo  [OK] .env 配置文件已存在
)

REM ---- 构建并启动容器 ----
echo.
echo  ── 正在构建并启动容器（首次构建约需 3-8 分钟）──
echo.

docker compose up -d --build
if errorlevel 1 (
    echo.
    echo  [X] 启动失败，请检查上方错误信息
    echo      常见原因：端口 80 被占用 / Docker 资源不足
    echo      如端口冲突，可在 .env 中设置 FRONTEND_PORT=8080
    echo.
    pause
    exit /b 1
)

REM ---- 等待后端就绪 ----
echo.
echo  ── 等待后端服务就绪 ──
set /a tries=0

:waitloop
set /a tries+=1
if %tries% gtr 40 (
    echo  [!] 服务启动超时，请检查日志: docker compose logs backend
    goto :show_info
)
timeout /t 3 /nobreak >nul
curl.exe -s -o nul http://localhost:8000/health 2>nul
if errorlevel 1 (
    echo  · 等待中... 第 %tries% 次尝试
    goto :waitloop
)
echo  [OK] 后端服务已就绪

:show_info
echo.
echo  ════════════════════════════════════════════════════════════
echo.
echo    系统已启动！
echo.
echo    前端页面:  http://localhost
echo    后端 API:  http://localhost:8000
echo    API 文档:  http://localhost:8000/docs
echo.
echo    默认登录:  用户名 admin  密码 admin123
echo.
echo    停止系统:  双击 docker-stop.bat
echo    查看日志:  docker compose logs -f
echo.
echo    提示: 如需 AI 生成功能，请在 .env 中设置 OPENAI_API_KEY
echo          修改后执行: docker compose up -d 重新生效
echo.
echo  ════════════════════════════════════════════════════════════
echo.

REM ---- 打开浏览器 ----
start http://localhost

pause
