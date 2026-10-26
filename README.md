# Insurance Product Tools

보험 상품 기초서류 검색·분석 웹앱과 하나생명 공시실 다운로드 도구를 함께 관리합니다.

저장소: [lwhdngus-design/insurance-product-tools](https://github.com/lwhdngus-design/insurance-product-tools) · [통합본 ZIP 받기](https://github.com/lwhdngus-design/insurance-product-tools/archive/refs/heads/main.zip)

```text
insurance-product-tools/       # 압축을 푼 폴더 이름은 달라도 됩니다.
├─ product-search/             # 기존 poc-2an: PDF 검색, 상품 분석·비교, 로컬 AI 질문
├─ hanalife-docs/              # 기존 261014의 다운로드 도구
├─ product-documents/          # 기본 다운로드 위치 (실행 시 생성, Git 제외)
├─ start-search.bat            # 내 기초서류로 검색 앱 실행
├─ start-sample.bat            # 교육용 가상 PDF로 검색 앱 실행
├─ download-docs.bat           # 패키지·브라우저 준비 후 공시실 다운로드
├─ update.bat                  # 앱·다운로드 도구·교육자료 원본 업데이트
└─ education/index.html        # 회사 교육자료 POC 전체 HTML 원본
```

## 같은 주소에서 갱신되는 교육자료와 웹 데모

- 교육자료 POC: https://lwhdngus-design.github.io/insurance-product-tools/poc/
- 웹 데모: https://lwhdngus-design.github.io/insurance-product-tools/demo/
- 게시 버전: https://lwhdngus-design.github.io/insurance-product-tools/publication.json

앱과 관련 교육자료를 같은 커밋으로 수정하고 GitHub에 반영하면, Actions가 둘을 함께 검증·게시합니다. 교육자료의 시연 링크도 같은 데모를 가리킵니다. 자동 게시가 설명문이나 캡처를 스스로 다시 작성하는 것은 아니며, 앞으로의 작업에서는 `AGENTS.md`에 따라 관련 교육자료도 함께 수정합니다. 기존 Claude 게시본은 별도 사본으로 유지합니다.

PC는 인터넷 연결 후 최상위 `update.bat` 또는 기존 `product-search\update.bat`을 실행할 때 갱신됩니다. GitHub 변경이 PC에 원격으로 즉시 적용되는 방식은 아닙니다. 최초 전환에는 최신 통합 ZIP을 새 폴더에 풀어 사용하세요.

관리·게시·문제 해결: [게시 안내](docs/PUBLISHING.md).

## Windows에서 사용하기

Python 3.9 이상과 Chrome 또는 Edge를 준비합니다. Python 설치 시 PATH 추가를 선택합니다.

1. 처음에는 `start-sample.bat`을 실행해 가상 상품 20개·PDF 82개가 열리는지 확인합니다.
2. 인터넷 되는 PC에서 `download-docs.bat`을 실행하면 공시실 서류를 `product-documents`에 저장합니다.
3. `start-search.bat`을 실행하고 다운로드된 `product-documents` 폴더를 연결합니다. 이미 다른 폴더가 연결되어 있으면 `product-search\change-folder.bat`으로 바꿉니다.

다운로드는 먼저 소량으로 확인하는 것을 권장합니다. 탐색기에서 `hanalife-docs` 폴더를 열고 주소창에 `cmd`를 입력한 뒤 실행합니다.

```bat
python -m pip install -r requirements.txt
python hanalife_download.py --limit 3
python hanalife_download.py
```

회사 PC의 이전 다운로드를 이어받으려면 **기존 서류와 download_log.csv가 들어 있는 폴더**를 지정하세요. 새 기본 위치에는 이전 기록이 없으므로 처음부터 받습니다.

```bat
python hanalife_download.py --out "D:\기존 상품기초서류"
```

검색 앱은 PDF.js와 Python 기본 라이브러리로 동작합니다. 로컬 AI(Ollama)는 선택 사항이며, 다운로드와 업데이트를 제외한 검색·분석은 오프라인으로 사용할 수 있습니다.

## 이전 버전에서 옮기기

- `poc-2an`은 `product-search`로 이름이 바뀌었습니다.
- 다운로드 도구는 같은 저장소의 `hanalife-docs`에 포함됩니다. 261014를 따로 받을 필요가 없습니다.
- ZIP으로 설치한 이전 버전은 통합 ZIP을 새 폴더에 풀어 사용하세요. 필요하면 예전 `poc-2an`의 `docs-folder.txt`와 `.docs-cache`를 새 `product-search`에 복사해 연결 설정·색인을 유지할 수 있습니다. 원본 PDF와 `download_log.csv`는 그대로 유지하세요.
- 이후에는 `product-search\update.bat`으로 업데이트합니다. ZIP 방식은 검색 앱과 다운로드 도구를 함께 갱신하며, 기존 설정·색인·다운로드 결과는 삭제하지 않습니다.
- GitHub 저장소 이름을 변경한 뒤에도 이전 GitHub 주소는 리디렉션될 수 있지만, 기존 파일 안의 `poc-2an` 경로는 자동으로 바뀌지 않습니다.

## 개발 및 검증

```sh
cd product-search
python3 serve.py --sample --no-browser
```

Node Playwright가 준비된 개발 환경에서는 `node tests/run-ai-questions.js`로 기존 질문 1,000개를 검증합니다. 러너가 생성한 `tests/ai-results.json`에서 실제 통과 개수도 확인해야 합니다.

다운로드 도구는 Python Playwright가 필요합니다. Linux에서 시스템 Chromium을 사용할 때는 `--chrome /usr/bin/chromium`을 지정할 수 있습니다.

상세 사용법: [상품 검색·분석](product-search/README.md), [공시실 다운로드](hanalife-docs/README.md).
기존 루트의 `index.html`과 `images/`는 이전 랜딩 페이지 파일입니다.
