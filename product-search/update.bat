@echo off
chcp 65001 >nul
rem 최신 버전 받기: git으로 받은 폴더는 git pull, ZIP으로 받은 폴더는 최신 ZIP을 받아 덮어씀
rem (자기 자신도 덮어쓰므로 임시 폴더에 복사본을 만들어 그것으로 실행)
if /i not "%~1"=="--run" (
  copy /y "%~f0" "%TEMP%\insurance_product_tools_update.bat" >nul
  "%TEMP%\insurance_product_tools_update.bat" --run "%~dp0."
  exit /b
)
set "APPDIR=%~f2"
cd /d "%APPDIR%"
set "BR=main"
set "ZIPURL=https://github.com/lwhdngus-design/insurance-product-tools/archive/refs/heads/main.zip"
echo 앱 폴더: %APPDIR%
echo.

where git >nul 2>nul || goto zip
git rev-parse --is-inside-work-tree >nul 2>nul || goto zip
echo [git] 최신 버전을 받습니다...
git fetch origin %BR% || goto fail
git checkout %BR% || goto fail
git pull --ff-only origin %BR% || goto fail
goto done

:zip
echo [ZIP] git으로 받은 폴더가 아니어서 최신 ZIP을 내려받아 덮어씁니다.
echo       폴더 설정(docs-folder.txt)과 검색 색인(.docs-cache)은 그대로 둡니다.
set "TMPD=%TEMP%\insurance_product_tools_update"
if exist "%TMPD%" rmdir /s /q "%TMPD%"
mkdir "%TMPD%"
set "ZIPFILE=%TMPD%\app.zip"
rem 회사 보안(인증서 검사·프록시)에 따라 되는 방법이 달라 차례로 시도
echo  - 받기 1/3: PowerShell
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol='Tls12'; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Uri '%ZIPURL%' -OutFile '%ZIPFILE%'" >nul 2>nul
if not errorlevel 1 goto unzip
echo  - 받기 2/3: curl
where curl.exe >nul 2>nul || goto bits
curl.exe -fsSL -o "%ZIPFILE%" "%ZIPURL%" >nul 2>nul
if not errorlevel 1 goto unzip
:bits
echo  - 받기 3/3: BITS
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Start-BitsTransfer -Source '%ZIPURL%' -Destination '%ZIPFILE%'" >nul 2>nul
if not errorlevel 1 goto unzip

rem 이 창에서는 못 받으면: 크롬으로 받게 하고 다운로드 폴더의 ZIP을 사용
echo.
echo [안내] 회사 보안 때문에 이 창에서는 직접 받을 수 없습니다.
echo        크롬으로 최신 ZIP을 엽니다. 다운로드가 끝나면 이 창으로 돌아와 아무 키나 누르세요.
start "" "%ZIPURL%"
pause
set "ZIPFILE="
for /f "usebackq delims=" %%F in (`powershell -NoProfile -Command "$d=(New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path; if(-not $d){$d=Join-Path $env:USERPROFILE 'Downloads'}; Get-ChildItem -LiteralPath $d -File -ErrorAction SilentlyContinue ^| Where-Object { $_.Name -like '261007-*.zip' -or $_.Name -like 'insurance-product-tools-*.zip' } ^| Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-3) } ^| Sort-Object LastWriteTime -Descending ^| Select-Object -First 1 -ExpandProperty FullName"`) do set "ZIPFILE=%%F"
if not defined ZIPFILE goto zipfail
echo  - 다운로드 폴더의 ZIP 사용: %ZIPFILE%

:unzip
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Expand-Archive -Force -LiteralPath '%ZIPFILE%' -DestinationPath '%TMPD%\x'"
if errorlevel 1 goto zipfail
set "SRC="
for /d %%D in ("%TMPD%\x\*") do set "SRC=%%D\product-search"
if not defined SRC goto zipfail
if not exist "%SRC%\index.html" goto zipfail
robocopy "%SRC%" "%APPDIR%" /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto zipfail
rem 통합 ZIP의 다운로드 도구도 함께 갱신 (기존 PDF와 download_log.csv는 유지)
for %%D in (hanalife-docs education scripts) do (
  if not exist "%SRC%\..\%%D\" goto zipfail
  robocopy "%SRC%\..\%%D" "%APPDIR%\..\%%D" /E /NFL /NDL /NJH /NJS /NP >nul
  if errorlevel 8 goto zipfail
)
for %%F in (start-search.bat start-sample.bat download-docs.bat update.bat README.md AGENTS.md site.json) do (
  copy /y "%SRC%\..\%%F" "%APPDIR%\..\%%F" >nul
  if errorlevel 1 goto zipfail
)
rmdir /s /q "%TMPD%"
goto done

:zipfail
echo.
echo [업데이트 못 함] 최신 ZIP을 받지 못했거나 다운로드 폴더에서 찾지 못했습니다.
echo  1) 크롬 주소창에 아래 주소를 넣어 최신 ZIP을 받습니다.
echo     %ZIPURL%
echo  2) 압축을 풀고 product-search와 hanalife-docs 폴더를 통합 폴더에 덮어씁니다. 설정과 다운로드 결과는 유지하세요.
echo  3) 검은 창을 모두 닫고 start.bat 으로 다시 실행합니다.
goto end

:fail
echo.
echo [업데이트 실패] 위에 나온 메시지를 캡처해서 보내 주세요.
echo  "local changes would be overwritten" 이 보이면 앱 폴더의 파일을 직접 고친 것이 있다는 뜻입니다.
goto end

:done
echo.
echo 업데이트 완료. 받은 앱 버전:
findstr /c:"const APP_VERSION" "%APPDIR%\layout.js"
echo.
echo 열려 있는 앱 창(검은 창)을 모두 닫고 start.bat 으로 다시 실행하세요.
echo 앱의 [기초서류 연결] 화면 "앱 버전"에서도 확인할 수 있습니다.

:end
echo.
pause
