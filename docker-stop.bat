@echo off
chcp 65001 >nul
title 领域知识多智能体系统 - Docker 停止

echo.
echo  正在停止所有 Docker 容器...
echo.

cd /d "%~dp0"
docker compose down

if errorlevel 1 (
    echo.
    echo  [X] 停止失败，请检查上方错误信息
    echo.
    pause
    exit /b 1
)

echo.
echo  [OK] 所有服务已停止，数据已保留在 Docker 卷中
echo       下次双击 docker-start.bat 即可重新启动
echo.
pause
