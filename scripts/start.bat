@echo off
chcp 65001 >nul
rem 双击或在 cmd 里运行：启动后端(8000) 与 Nginx(8080)
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev-start.ps1" %*
