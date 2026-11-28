@echo off
chcp 65001 >nul
rem 双击或在 cmd 里运行：停止后端与 Nginx
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev-stop.ps1" %*
