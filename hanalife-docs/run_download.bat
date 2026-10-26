@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo [1/3] Python 패키지 설치
python -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo [2/3] 크롬(Playwright) 브라우저 설치
python -m playwright install chromium
if errorlevel 1 echo [안내] 브라우저 설치 실패 시 설치된 크롬 또는 엣지로 실행을 시도합니다.
echo [3/3] 하나생명 기초서류 다운로드 시작
python hanalife_download.py %*
if errorlevel 1 goto fail
pause
exit /b 0

:fail
echo [실패] 위 오류 메시지를 확인해 주세요.
pause
exit /b 1
