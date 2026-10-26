# 앱·교육자료·웹 데모 업데이트

소스는 한 GitHub 저장소에서 관리합니다. 앱 기능을 수정할 때 교육자료의 관련 설명도 함께 수정하고, 같은 커밋을 게시합니다. 글과 캡처를 자동으로 새로 작성하는 기능은 아니며, 수정한 원본의 빌드·검증·배포를 자동화합니다.

## 사용할 주소

- 교육자료: https://lwhdngus-design.github.io/insurance-product-tools/poc/
- 웹 데모: https://lwhdngus-design.github.io/insurance-product-tools/demo/
- 게시 버전 확인: https://lwhdngus-design.github.io/insurance-product-tools/publication.json
- 코드와 ZIP: https://github.com/lwhdngus-design/insurance-product-tools

주소는 고정이며 이후 정상 배포가 완료되면 같은 주소의 내용이 갱신됩니다. 기존 루트 홈페이지는 보존합니다. 기존 Claude 아티팩트는 별도 사본으로 남고 이 배포 과정에서 변경하지 않습니다.

## 평소 사용

1. 이 대화에서 앱 수정사항을 요청합니다. 작업 지침(`AGENTS.md`)에 따라 관련 교육자료도 같은 작업에서 수정합니다.
2. 앱과 자료를 검증하고 릴리스 브랜치에 커밋·푸시합니다.
3. GitHub Actions의 **Publish POC and demo**가 두 자료를 함께 빌드·검증·게시합니다. 실패하면 이전 정상 게시본을 유지합니다.
4. 교육자료와 데모는 같은 주소로 확인합니다. `publication.json`의 `commit`은 실제 게시된 버전입니다.
5. PC에서는 인터넷 연결 후 최상위 `update.bat` 또는 `product-search\update.bat`을 실행하고 앱을 다시 엽니다. 화면이 이전 모습이면 Ctrl+F5를 누릅니다.

GitHub에 푸시해도 꺼져 있거나 연결되지 않은 회사 PC의 파일은 원격으로 바뀌지 않습니다. PC 업데이트는 사용자가 `update.bat`을 실행할 때 진행합니다. 내부망에서는 인터넷 되는 PC에서 ZIP을 받아 옮기는 기존 방식을 사용합니다.

## 관리할 원본

| 대상 | 수정할 파일 |
|---|---|
| 상품 검색·분석·질문 | `product-search/` |
| 공시실 다운로드 | `hanalife-docs/` |
| 교육자료 전체 HTML | `education/index.html` |
| 사이트·저장소·브랜치 설정 | `site.json` |
| 게시 자동화 | `.github/workflows/publish.yml` |

교육자료는 첨부한 전체 HTML을 기반으로 하며, 내장 이미지 26개와 스타일·스크립트 원본을 보존했습니다. 교육자료의 시연 링크는 새 `/demo/` 주소를 사용합니다. 기존 캡처와 검증 수치는 과거 기록으로 유지합니다. 보호된 이미지·스타일·스크립트의 기준 해시는 `education/protected-assets.json`에 저장하며, 사용자가 변경을 요청하지 않았다면 기준값을 새 값으로 덮어 검증 실패를 숨기지 마세요.

릴리스 브랜치는 `main`입니다. 기존 main 홈페이지 파일은 보존하면서 앱·교육자료 소스를 함께 관리합니다. 이전 `claude/excel-2an-sheet-format-svwm4c` 브랜치는 기존 update.bat이 새 업데이트 경로를 받을 수 있도록 전환용 커밋을 남깁니다.

## 로컬 빌드

Python 3.9 이상과 Git이 필요하며 추가 Python 패키지는 없습니다.

```sh
python3 scripts/build_site.py
python3 scripts/check_site.py
```

`_site/`는 생성물이며 Git에 올리지 않습니다. 게시 대상은 추적된 공개 파일만 선택해 만듭니다. 실제 회사 PDF·캐시·폴더 설정·다운로드 로그·비밀값은 포함하지 않습니다. `--base-url`로 다른 게시 경로를 지정해도 교육자료와 데모의 연결을 함께 바꿉니다.

## 처음 설치하거나 기존 ZIP 버전에서 전환

처음에는 최신 통합 ZIP을 새 폴더에 풀어 최상위 `update.bat`까지 받는 것을 권장합니다. 기존 PDF와 `download_log.csv`는 유지하고 이전 저장 폴더를 계속 지정하세요. 필요하면 이전 `product-search`의 `docs-folder.txt`와 `.docs-cache`를 복사해 설정과 색인을 이어갑니다.

그다음부터는 `update.bat`을 사용합니다. Git 설치본은 fast-forward만 허용해 로컬 수정과 충돌하면 멈추며, ZIP 설치본은 앱·다운로드 도구·교육자료 원본을 함께 복사합니다. 사용자 문서나 캐시를 삭제하는 미러 동기화는 하지 않습니다. Windows 배치 실행 자체는 Windows PC에서 확인해야 합니다.

## 배포 상태와 문제 해결

- 저장소의 **Actions → Publish POC and demo**에서 빌드와 배포가 모두 성공했는지 확인합니다.
- 저장소 **Settings → Pages**의 게시 방식은 **GitHub Actions**입니다. 최초 전환·권한 변경에는 저장소 관리 권한이 필요합니다.
- `github-pages` 환경에 배포 브랜치 제한이 있으면 위 릴리스 브랜치를 허용해야 합니다. 기존 승인 요구사항은 제거하지 않습니다.
- Actions의 실패 원인을 고친 뒤 다시 실행합니다. 푸시 성공과 실제 게시 성공은 별개입니다.
- 새 화면이 안 보이면 `publication.json`의 커밋과 최신 커밋을 비교하고 새로고침합니다. 회사 네트워크에서 GitHub Pages가 차단되면 해당 공개 사이트에 대한 접근 허용이 필요합니다.
