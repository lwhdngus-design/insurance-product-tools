@echo off
chcp 65001 >nul
call "%~dp0product-search\start-sample.bat" %*
exit /b %errorlevel%
