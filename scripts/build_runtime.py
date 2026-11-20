"""Build a transparent end-user package, retaining original source file extensions."""
import csv
import argparse
import hashlib
import io
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "insurance-product-tools-runtime/"
PYTHON_RUNTIME = {"serve.py", "word_docs.py"}


def role(name):
    path = Path(name)
    if path.suffix == ".py":
        return "필수", "검색 서버" if path.name == "serve.py" else "Word 본문 읽기·변환 모듈"
    if path.suffix == ".ps1":
        return "Windows Word 미리보기 시 사용", "Microsoft Word 자동화"
    if path.suffix == ".bat":
        return "실행 시작", "Python 서버 실행"
    if path.suffix == ".pdf":
        return "교육용", "가상 상품 샘플 PDF"
    if path.name == "main-logic.txt":
        return "교육용", "소스 코드 참조 문서(실행하지 않음)"
    if path.suffix == ".csv":
        return "앱 데이터", "특징 사전·가상 데이터"
    return "앱 자원", "화면·검색 코드·로컬 PDF 라이브러리·이미지"


def build(output=None):
    output = Path(output) if output else ROOT / "downloads/insurance-product-tools-runtime.zip"
    tracked = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"]).decode().split("\0")
    files = {}
    for name in filter(None, tracked):
        path = Path(name)
        if not name.startswith("product-search/") or "tests" in path.parts:
            continue
        tail = Path(*path.parts[1:])
        allowed = tail.suffix in {".html", ".js", ".css", ".png", ".jpg", ".svg", ".txt", ".csv"}
        allowed |= len(tail.parts) == 1 and tail.name in PYTHON_RUNTIME | {"word-preview.ps1"}
        allowed |= tail.parts[0] == "lib" and tail.name == "pdfjs-LICENSE"
        allowed |= tail.parts[0] == "sample-기초서류폴더" and tail.suffix == ".pdf"
        if not allowed or any(p.startswith(".") for p in tail.parts):
            continue
        source = ROOT / path
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise ValueError("unexpected source path: " + name)
        files[name] = source.read_bytes()
    for name in PYTHON_RUNTIME:
        assert "product-search/" + name in files, "missing runtime module: " + name
    for name, options in (("start-search.bat", ""), ("start-sample.bat", " --sample")):
        # data.js is already built. Developer build-data.py is not a runtime dependency.
        text = '@echo off\nchcp 65001 >nul\ncd /d "%~dp0product-search"\npython serve.py' + options + '\npause\n'
        files[name] = text.replace("\n", "\r\n").encode("utf-8")
    inventory = io.StringIO(newline="")
    writer = csv.writer(inventory, lineterminator="\n")
    writer.writerow(["파일", "확장자", "구분", "용도", "바이트", "SHA256"])
    for name, data in sorted(files.items()):
        writer.writerow([name, Path(name).suffix, *role(name), len(data), hashlib.sha256(data).hexdigest()])
    files["READ_ME.txt"] = '''Insurance Product Tools 실행용 배포 구성

개발·시험·게시 도구, 공시실 다운로드 도구, 분할압축 도구는 제외했습니다.
Python 소스는 serve.py와 word_docs.py 2개이며 본래 확장자로 포함됩니다.
Windows Word 미리보기에는 word-preview.ps1도 사용합니다.
기능에 필요한 .js·.html·로컬 라이브러리·데이터와 교육용 가상 PDF는 유지합니다.
main-logic.txt는 기존 교육 화면의 소스 참조 문서이며 실행하지 않습니다.
전체 파일명·확장자·용도·해시는 FILES.csv에서 확인할 수 있습니다.

반입·실행:
회사 정책이 .py를 차단하면 이 배포본도 승인된 경로/형식이 확인되기 전에는 반입할 수 없습니다.
회사 IT에 Python 소스 2개, .ps1 및 실행 파일의 반입·실행 허용 여부를 확인하세요.
현재 반입 정책에 맞춰 승인된 설치/배포 방식이 정해지면 그 규격으로 배포해야 합니다.

회사에서 허용한 배포 경로로 설치한 후 Python 3.9 이상으로 start-search.bat을 실행합니다.
새 배포본은 별도 폴더에 풀고 기존 Word·PDF 원본 폴더를 연결하세요.
기존 문서·docs-folder.txt·.docs-cache는 그대로 보존하세요.
Python 설치파일은 포함하지 않습니다.
Word 그림 보기는 Windows Microsoft Word 또는 LibreOffice가 필요합니다.
실제 회사 문서, 다운로드 기록, 계정정보는 포함하지 않습니다.
'''.encode("utf-8-sig")
    notice = files["READ_ME.txt"]
    writer.writerow(["READ_ME.txt", ".txt", "안내문", "설치 및 회사 반입 검토 안내", len(notice), hashlib.sha256(notice).hexdigest()])
    files["FILES.csv"] = inventory.getvalue().encode("utf-8-sig")
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(PREFIX + name, data)
    output.with_name(output.stem + "-files.csv").write_bytes(files["FILES.csv"])
    check(output)
    return output


def check(output):
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        names = [n.removeprefix(PREFIX) for n in archive.namelist()]
        assert {n for n in names if n.endswith(".py")} == {"product-search/" + n for n in PYTHON_RUNTIME}
        assert not any(n.endswith((".cjs", ".md", ".yml", ".yaml", ".doc", ".docx", ".hwp", ".hwpx")) for n in names)
        assert not any(part in {"tests", ".docs-cache", ".github", "product-documents"} for n in names for part in Path(n).parts)
        for n in names:
            if n.endswith(".pdf"):
                assert n.startswith("product-search/sample-기초서류폴더/")
        listed = set()
        for row in csv.DictReader(io.StringIO(archive.read(PREFIX + "FILES.csv").decode("utf-8-sig"))):
            listed.add(row["파일"])
            data = archive.read(PREFIX + row["파일"])
            assert hashlib.sha256(data).hexdigest() == row["SHA256"]
            assert len(data) == int(row["바이트"])
            if row["파일"].startswith("product-search/"):
                assert data == (ROOT / row["파일"]).read_bytes(), "stale runtime file: " + row["파일"]
        assert listed | {"FILES.csv"} == set(names), "unlisted runtime file"
        assert Path(output).with_name(Path(output).stem + "-files.csv").read_bytes() == archive.read(PREFIX + "FILES.csv"), "stale standalone inventory"
    print(f"PASS: runtime package {len(names)} files, 2 required .py, no .cjs, original extensions and hashes; {Path(output).stat().st_size:,} bytes")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check(ROOT / "downloads/insurance-product-tools-runtime.zip")
    else:
        print(build())
