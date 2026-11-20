기초서류를 500MB 미만 ZIP으로 나눠 내부망으로 전송하기

1. 도구 ZIP을 내려받아 압축을 풉니다.
2. 기초서류 다운로드 프로그램이 실행 중이면 종료합니다.
3. 1_pack_490MB.bat을 더블클릭합니다.
4. 폴더 선택창에서 원본 product-documents 폴더를 선택합니다.
5. 완료 후 원본 옆에 product-documents-transfer-날짜-번호 폴더가 열립니다.

Python 3.9 이상이 필요합니다. 웹앱에서 사용하던 Python이 있으면 추가 설치는 없습니다.
인터넷이나 추가 Python 패키지는 사용하지 않습니다.
각 ZIP은 최대 490,000,000바이트(490MB)로, 500MB 전송 한도에 여유를 둡니다.
파일 크기와 압축률에 따라 ZIP은 한도보다 작을 수 있습니다.
원본 PDF, 하위 폴더 구조, download_log.csv 등 파일을 포함하며 원본은 보존합니다.
다시 실행하면 별도의 새 결과 폴더를 만듭니다.

내부망으로 옮길 파일:
- product-documents-001.zip, product-documents-002.zip 등 모든 ZIP
- manifest.json, documents_transfer.py, 2_restore.bat, 사용방법.txt
한 번의 전송 합계가 500MB 제한이면 ZIP을 하나씩 옮기세요.

내부망에서 복원:
1. 위 파일들을 모두 같은 폴더에 모읍니다.
2. 2_restore.bat을 실행합니다. Python 3.9 이상이 필요합니다.
3. restored-날짜 폴더 아래 복원된 product-documents를 검색 앱에 연결합니다.
복원 도구는 ZIP 및 복원 파일의 SHA-256을 검사합니다.
일반 파일은 독립 ZIP이며 같은 대상 폴더에 직접 풀 수도 있습니다.
파일 하나가 한도보다 큰 경우는 자동으로 조각내므로 반드시 2_restore.bat으로 복원하세요.
INCOMPLETE.txt가 있는 결과 폴더는 완료되지 않았으므로 전송하거나 사용하지 마세요.
경로 길이 오류가 나면 전송 폴더를 C:\기초서류전송처럼 짧은 경로에 옮겨 복원하세요.

다운로드 기록 CSV는 그대로 보존하지만 기록 안의 기존 PC 경로를 자동으로 바꾸지는 않습니다.
명령줄에서 원본 폴더를 지정할 수도 있습니다:
  python documents_transfer.py --source "D:\기초서류"

소스 변경 후 배포 ZIP을 다시 만들려면 저장소 루트에서 실행합니다:
  python tools/documents-transfer/build_bundle.py
