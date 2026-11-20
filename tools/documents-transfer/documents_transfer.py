"""Pack documents into independent ZIPs below the transfer limit (stdlib only)."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import uuid
from datetime import datetime
import zipfile


DEFAULT_SOURCE = None
DEFAULT_LIMIT = 490_000_000  # decimal MB; always below both common definitions of 500 MB
BLOCK = 1024 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK), b""):
            digest.update(block)
    return digest.hexdigest()


def bound(size, name):
    # Conservative DEFLATE bound plus both ZIP headers, UTF-8 names and ZIP64 extras.
    return size + size // 100 + 128 + 512 + 2 * len(name.encode("utf-8"))


def unique_directory(parent, prefix):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = parent / f"{prefix}-{stamp}-{uuid.uuid4().hex[:6]}"
    output.mkdir(parents=True, exist_ok=False)
    return output


def make_bat(restore=False):
    option = '--restore "%~dp0manifest.json"' if restore else ''
    text = f'''@echo off
chcp 65001 >nul
setlocal
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 "%~dp0documents_transfer.py" {option}
goto finished
:use_python
python "%~dp0documents_transfer.py" {option}
:finished
if errorlevel 1 echo [실패] 위 오류를 확인해 주세요. 이 창은 결과 확인 후 닫아 주세요.
echo.
pause
'''
    text = "\n".join(line.rstrip() for line in text.splitlines()) + "\n"
    return text.replace("\n", "\r\n").encode("utf-8")


def source_files(source):
    files = []
    for root, dirs, names in os.walk(source, followlinks=False, onerror=lambda exc: (_ for _ in ()).throw(exc)):
        dirs.sort()
        for name in dirs + sorted(names):
            path = Path(root) / name
            if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                raise ValueError(f"연결 폴더/파일은 먼저 일반 폴더로 준비해 주세요: {path}")
        for name in sorted(names):
            path = Path(root) / name
            if not path.is_file():
                raise ValueError(f"일반 파일이 아닙니다: {path}")
            stat = path.stat()
            files.append((path, stat.st_size, stat.st_mtime_ns))
    return files


def pack(source, limit=DEFAULT_LIMIT):
    source = source.expanduser().resolve(strict=True)
    if not source.is_dir():
        raise ValueError(f"폴더가 아닙니다: {source}")
    if limit < 10_000:
        raise ValueError("압축 한도가 너무 작습니다.")
    files = source_files(source)
    if not files:
        raise ValueError("압축할 파일이 없습니다.")
    total = sum(size for _, size, _ in files)
    print(f"원본: {source}\n파일 {len(files):,}개 / {total / 1_000_000:,.1f} MB", flush=True)
    print("원본을 삭제하거나 이동하지 않습니다. 압축 중에는 다운로드 프로그램을 종료해 주세요.", flush=True)
    output = unique_directory(source.parent, source.name + "-transfer")
    print(f"저장: {output}", flush=True)
    manifest = {"version": 1, "limit_bytes": limit, "root": source.name,
                "archives": [], "files": [], "split_files": 0}
    archive = None
    temporary = None
    archive_name = ""
    predicted = 22

    def finish_archive():
        nonlocal archive
        if archive is None:
            return
        archive.close()
        archive = None
        size = temporary.stat().st_size
        if size > limit:
            raise ValueError(f"한도 초과로 전송 파일 생성을 중단했습니다: {temporary.name}")
        with zipfile.ZipFile(temporary) as check:
            bad = check.testzip()
            if bad:
                raise ValueError(f"압축 검증 실패: {bad}")
        digest = sha256(temporary)
        temporary.rename(output / archive_name)
        manifest["archives"].append({"name": archive_name, "size": size, "sha256": digest})
        print(f"  완료: {archive_name} / {size / 1_000_000:,.2f} MB / 검증 통과", flush=True)

    try:
        for file_index, (path, size, modified) in enumerate(files, 1):
            name = path.relative_to(source.parent).as_posix()
            chunk_template = f"__transfer_parts__/{file_index:08d}/000001.bin"
            capacity = (limit - 22 - bound(0, chunk_template)) * 100 // 101 - 128
            split = bound(size, name) + 22 > limit
            if split:
                manifest["split_files"] += 1
            record = {"path": name, "size": size, "parts": []}
            digest = hashlib.sha256()
            remaining = size
            part_index = 0
            with path.open("rb") as original:
                while remaining or part_index == 0:
                    part_index += 1
                    entry_name = f"__transfer_parts__/{file_index:08d}/{part_index:06d}.bin" if split else name
                    length = min(remaining, capacity) if split else remaining
                    needed = bound(length, entry_name)
                    if needed + 22 > limit:
                        raise ValueError(f"파일 경로가 너무 길거나 한도가 너무 작습니다: {name}")
                    if archive is not None and predicted + needed > limit:
                        finish_archive()
                    if archive is None:
                        archive_name = f"product-documents-{len(manifest['archives']) + 1:03d}.zip"
                        temporary = output / (archive_name + ".partial")
                        archive = zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6)
                        predicted = 22
                    info = zipfile.ZipInfo(entry_name)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.date_time = datetime.fromtimestamp(path.stat().st_mtime).timetuple()[:6]
                    if info.date_time[0] < 1980 or info.date_time[0] > 2107:
                        info.date_time = (1980, 1, 1, 0, 0, 0)
                    with archive.open(info, "w", force_zip64=True) as target:
                        left = length
                        while left:
                            data = original.read(min(BLOCK, left))
                            if not data:
                                raise ValueError(f"압축 중 원본이 변경됐습니다: {path}")
                            target.write(data)
                            digest.update(data)
                            left -= len(data)
                    record["parts"].append({"archive": archive_name, "entry": entry_name})
                    predicted += needed
                    remaining -= length
                if original.read(1):
                    raise ValueError(f"압축 중 원본 크기가 변경됐습니다: {path}")
            now = path.stat()
            if (now.st_size, now.st_mtime_ns) != (size, modified):
                raise ValueError(f"압축 중 원본이 변경됐습니다: {path}")
            record["sha256"] = digest.hexdigest()
            manifest["files"].append(record)
            if file_index % 100 == 0 or file_index == len(files):
                print(f"  처리: {file_index:,}/{len(files):,}개", flush=True)
        finish_archive()
        # Detect additions/deletions/changes before claiming a complete folder snapshot.
        if source_files(source) != files:
            raise ValueError("압축 중 원본 폴더가 변경됐습니다. 다운로드를 종료한 뒤 다시 실행하세요.")
        (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.copyfile(Path(__file__), output / "documents_transfer.py")
        (output / "2_restore.bat").write_bytes(make_bat(restore=True))
        guide = f'''기초서류 내부망 전송 파일

ZIP 개수: {len(manifest['archives'])}개
원본 파일: {len(files)}개
ZIP 크기 한도: {limit:,}바이트 (기본 490MB, 500MB 미만)
단일 파일 분할: {manifest['split_files']}개

1. 이 폴더 안의 ZIP, manifest.json, documents_transfer.py, 2_restore.bat을 모두 내부망으로 옮기세요.
   한 번의 전송 총량도 500MB 제한이면 ZIP을 하나씩 전송하세요. 안내/복원 파일은 별도로 전송해도 됩니다.
2. 내부망에서 모든 파일을 한 폴더에 모은 뒤 2_restore.bat을 실행하세요.
   Python 3.9 이상이 필요합니다. 외부 인터넷이나 추가 패키지는 필요 없습니다.
3. 이 폴더 안의 restored-날짜 폴더에 {source.name}가 복원됩니다.
   이 {source.name} 폴더를 상품 검색 앱에 연결하세요.

보통 ZIP은 각각 독립 압축이며, 직접 같은 대상 폴더에 모두 풀 수도 있습니다.
단일 원본 파일이 한도보다 큰 경우에는 조각으로 저장되므로 반드시 2_restore.bat을 사용하세요.
복원 도구는 모든 ZIP의 크기/해시를 검사하고 원본 파일의 SHA-256을 검증해 원래 이름으로 복원합니다.
원본 폴더는 삭제/이동/수정하지 않았습니다. 다운로드 기록(download_log.csv)도 파일로 포함됩니다.
기록 안의 기존 PC 경로를 자동으로 변경하지는 않습니다.
경로 길이 오류가 나면 전송 폴더를 C:\\기초서류전송처럼 짧은 경로로 옮긴 뒤 복원하세요.
'''
        (output / "사용방법.txt").write_text(guide, encoding="utf-8-sig")
    except BaseException:
        if archive is not None:
            archive.close()
        (output / "INCOMPLETE.txt").write_text("압축이 완료되지 않았습니다. 이 폴더를 전송하지 말고 오류를 해결한 후 다시 실행하세요.\n", encoding="utf-8-sig")
        raise
    print(f"\n성공: ZIP {len(manifest['archives'])}개, 원본 {len(files):,}개. 모두 크기/압축 검증 통과.", flush=True)
    print(f"이 폴더의 파일들을 전송하세요:\n{output}", flush=True)
    return output


def safe_relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value:
        raise ValueError(f"올바르지 않은 복원 경로: {value}")
    return Path(*path.parts)


def restore(manifest_path):
    manifest_path = manifest_path.resolve(strict=True)
    folder = manifest_path.parent
    if (folder / "INCOMPLETE.txt").exists():
        raise ValueError("완료되지 않은 압축 폴더입니다.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("version") != 1:
        raise ValueError("지원하지 않는 전송 파일입니다.")
    archives = {}
    for item in manifest["archives"]:
        name = item["name"]
        if safe_relative(name).name != name:
            raise ValueError("올바르지 않은 ZIP 파일 이름입니다.")
        path = folder / name
        if path.stat().st_size != item["size"] or sha256(path) != item["sha256"]:
            raise ValueError(f"ZIP이 손상됐거나 전송이 덜 됐습니다: {name}")
        archives[name] = path
        print(f"전송 검증 통과: {name}", flush=True)
    output = unique_directory(folder, "restored")
    try:
        for index, record in enumerate(manifest["files"], 1):
            relative = safe_relative(record["path"])
            if relative.parts[0] != manifest["root"]:
                raise ValueError("원본 폴더를 벗어나는 복원 경로입니다.")
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            written = 0
            # Exclusive temporary files; never overwrite an existing user file.
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".restore-", delete=False) as dest:
                temporary = Path(dest.name)
                for part in record["parts"]:
                    with zipfile.ZipFile(archives[part["archive"]]) as archive:
                        with archive.open(part["entry"]) as original:
                            for data in iter(lambda: original.read(BLOCK), b""):
                                dest.write(data)
                                digest.update(data)
                                written += len(data)
                if written != record["size"] or digest.hexdigest() != record["sha256"]:
                    raise ValueError(f"복원한 파일의 검증에 실패했습니다: {record['path']}")
            if target.exists():
                raise ValueError(f"이미 존재하는 복원 파일입니다: {target}")
            temporary.rename(target)
            if index % 100 == 0 or index == len(manifest["files"]):
                print(f"복원: {index:,}/{len(manifest['files']):,}개", flush=True)
    except BaseException:
        (output / "INCOMPLETE.txt").write_text("복원이 완료되지 않았습니다. 오류를 확인하고 다시 실행하세요.\n", encoding="utf-8-sig")
        raise
    print(f"\n복원/원본 해시 검증 완료:\n{output / manifest['root']}", flush=True)
    return output


def choose_source():
    """Use a Windows folder picker; never embed a person's PC path in the tool."""
    if os.name == "nt":
        try:
            import tkinter
            from tkinter import filedialog
            window = tkinter.Tk()
            window.withdraw()
            try:
                window.attributes("-topmost", True)
                value = filedialog.askdirectory(parent=window, title="압축할 product-documents 폴더를 선택하세요", initialdir=str(Path.home()))
            finally:
                window.destroy()
            if not value:
                raise ValueError("폴더 선택을 취소했습니다.")
            return Path(value)
        except ImportError:
            pass
    value = input("압축할 product-documents 폴더 경로를 붙여넣고 Enter: ").strip().strip('"')
    if not value:
        raise ValueError("원본 폴더를 지정해 주세요.")
    return Path(value)


def main():
    parser = argparse.ArgumentParser(description="기초서류를 500MB 미만 ZIP으로 나눠 내부망으로 전송")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="원본 product-documents 폴더")
    parser.add_argument("--restore", type=Path, help="전송 폴더의 manifest.json을 사용해 복원")
    parser.add_argument("--limit-bytes", type=int, default=DEFAULT_LIMIT, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.restore:
        result = restore(args.restore)
    else:
        result = pack(args.source if args.source is not None else choose_source(), args.limit_bytes)
    if os.name == "nt":
        try:
            os.startfile(result)
        except OSError:
            pass  # The completed output path is also printed above.


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f"\n[실패] {exc}\n원본 파일은 변경하지 않았습니다.", file=sys.stderr, flush=True)
        sys.exit(1)
