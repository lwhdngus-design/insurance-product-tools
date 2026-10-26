# 하나생명 공시실 상품기초서류 다운로드

하나생명 공시실의 판매상품·판매중지상품 목록에서 상품요약서·사업방법서·보험약관을 다운로드합니다.
기존 `261014/261013/hanalife_docs` 도구를 상품 검색 앱과 같은 저장소의 `hanalife-docs`로 통합했습니다.

## Windows 실행

Python 3.9 이상이 필요합니다. 통합 폴더의 `download-docs.bat` 또는 이 폴더의 `run_download.bat`을 실행하면 패키지 설치·브라우저 준비·다운로드를 순서대로 진행합니다.

먼저 소량으로 확인하려면 이 폴더에서 주소창에 `cmd`를 입력하고 다음을 실행합니다.

```bat
python -m pip install -r requirements.txt
python hanalife_download.py --limit 3
python hanalife_download.py
```

Playwright 브라우저가 없으면 설치된 Chrome, Edge 순서로 실행을 시도합니다. 필요한 경우 브라우저를 설치하거나 실행파일을 직접 지정합니다.

```bat
python -m playwright install chromium
python hanalife_download.py --chrome "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

옵션:

```bat
python hanalife_download.py --status on       rem 판매상품만
python hanalife_download.py --status off      rem 판매중지상품만
python hanalife_download.py --limit 3         rem 목록별 최대 3행으로 시험
python hanalife_download.py --headed          rem 브라우저 창 표시
python hanalife_download.py --out "D:\상품기초서류"
```

`python` 명령이 없으면 Python 설치를 확인하거나 `py`로 바꿔 실행합니다.

## 저장 위치와 이어받기

기본 저장 위치는 통합 폴더의 `product-documents`입니다. 현재 작업 폴더나 Windows 사용자 이름에 영향을 받지 않습니다.

```text
insurance-product-tools/
├─ product-search/
├─ hanalife-docs/
└─ product-documents/
   ├─ 판매중/
   │  └─ 2026/2026.04.01/상품명/[보험약관] 원본파일명.pdf
   ├─ 판매중지/
   │  └─ 2014/2014.02.03/상품명/...
   └─ download_log.csv
```

같은 폴더로 다시 실행하면 이미 받은 서류는 건너뛰고 새 서류를 받습니다. 같은 상품이 판매중지로 바뀌면 재다운로드 없이 `판매중`에서 `판매중지`로 옮깁니다. 상품명·판매시작일·서류종류로 기존 기록을 확인합니다.

**이전에 받아 둔 파일을 이어받으려면 `--out`으로 이전 저장 폴더를 지정하세요.** 기존 파일과 `download_log.csv`를 유지해야 합니다. 이전 버전의 개인 PC 경로는 새 기본값으로 사용하지 않습니다.

화면의 `OK`는 성공, `MV`는 폴더 이동, `NG`는 실패입니다. 마지막 집계와 `download_log.csv`의 결과를 함께 확인하세요. 명령 종료만으로 다운로드 성공을 판단하지 않습니다.

## 검색 앱 연결

상위 폴더의 `start-search.bat`을 실행한 뒤 다운로드된 폴더를 지정합니다. 이미 다른 폴더가 설정되어 있으면 `product-search\change-folder.bat`으로 변경합니다.

## Linux 개발 환경

```sh
python3 -m pip install -r requirements.txt
python3 hanalife_download.py --chrome /usr/bin/chromium --limit 1 --out /path/to/documents
```

실제 공시실 다운로드에는 인터넷 접근이 필요합니다. 현재 클라우드 환경에서는 사이트 접속이 네트워크 정책으로 차단되어 실제 사이트 동작은 검증하지 못했으며, 로컬 테스트 페이지로 다운로드·이어받기·판매상태별 폴더 이동을 검증했습니다.
