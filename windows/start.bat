@echo off
rem 懒得笔记｜Windows 11 一键启动（薄包装：只负责转调 start.ps1）
rem 端口覆盖用法：set V2O_PORT=8900 && start.bat

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
exit /b %ERRORLEVEL%
