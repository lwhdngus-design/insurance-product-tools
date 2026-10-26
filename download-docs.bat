@echo off
chcp 65001 >nul
call "%~dp0hanalife-docs\run_download.bat" %*
exit /b %errorlevel%
