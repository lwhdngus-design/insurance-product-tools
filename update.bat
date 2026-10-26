@echo off
chcp 65001 >nul
call "%~dp0product-search\update.bat" %*
exit /b %errorlevel%
