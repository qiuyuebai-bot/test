@echo off
REM ============================================================
REM Windows 一键启动脚本（双击即可运行）
REM 调用跨平台 Node.js 启动器 scripts/start.mjs
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

REM 检测 Node.js
where node >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Node.js，请先安装 Node.js 18+ 后再运行
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

REM 解析参数（默认无参数 = 启动；--setup = 准备环境）
if "%~1"=="" (
    node scripts/start.mjs
) else (
    node scripts/start.mjs %*
)

REM 异常退出时保留窗口
if errorlevel 1 pause
