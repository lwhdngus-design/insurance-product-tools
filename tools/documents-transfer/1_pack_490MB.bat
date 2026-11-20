@echo off
chcp 65001 >nul
setlocal
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 "%~dp0documents_transfer.py"
goto finished
:use_python
python "%~dp0documents_transfer.py"
:finished
if errorlevel 1 echo [실패] 위 오류를 확인해 주세요. 이 창은 결과 확인 후 닫아 주세요.
echo.
pause
