"""Offline Office document text and on-demand PDF previews. Standard library only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import zipfile
from xml.etree import ElementTree as ET

EXTENSIONS = {".pdf", ".docx", ".doc", ".hwpx", ".hwp"}
NATIVE_EXTENSIONS = {".docx", ".hwpx"}
LINK_TYPES = ("산출방법서", "요율확인의뢰서")
READER_VERSION = "office-text-1"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
PREVIEW_LOCK = threading.Lock()


def link_only(path):
    return any(t in Path(path).name for t in LINK_TYPES)


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def xml_part(archive, name):
    info = archive.getinfo(name)
    if info.file_size > 64 * 1024 * 1024:
        raise ValueError("문서 XML이 너무 큽니다. 문서를 나눠 저장해 주세요.")
    return ET.fromstring(archive.read(name))


def paragraph_text(element):
    parts = []
    def walk(node):
        if node.tag in {W + "del", W + "moveFrom"}:
            return  # Track-changes deletions are not the current document text.
        if node.tag in {W + "t", M + "t"}:
            parts.append(node.text or "")
        elif node.tag == W + "tab":
            parts.append(" ")
        elif node.tag in {W + "br", W + "cr"}:
            parts.append("\n")
        else:
            for child in node:
                walk(child)
    walk(element)
    return "".join(parts).strip()


def docx_blocks(archive):
    root = xml_part(archive, "word/document.xml")
    blocks = []
    def walk(node):
        if node.tag in {W + "del", W + "moveFrom"}:
            return
        if node.tag == W + "p":
            text = paragraph_text(node)
            if text:
                blocks.append(text)
        elif node.tag == W + "tbl":
            # Keep cells in the same row together instead of mixing column values.
            rows = []
            for row in node.findall(W + "tr"):
                cells = []
                for cell in row.findall(W + "tc"):
                    cells.append(" / ".join(filter(None, (paragraph_text(p) for p in cell.iter(W + "p")))))
                if any(cells):
                    rows.append(" | ".join(cells))
            if rows:
                blocks.append("\n".join(rows))
        else:
            for child in node:
                walk(child)
    body = root.find(W + "body")
    if body is None:
        raise ValueError("DOCX 문서 본문을 찾지 못했습니다.")
    walk(body)
    for name in ("word/footnotes.xml", "word/endnotes.xml"):
        if name in archive.namelist():
            for p in xml_part(archive, name).iter(W + "p"):
                text = paragraph_text(p)
                if text:
                    blocks.append(text)
    return blocks


def read_native(path):
    """Text units are sections, never claims about Word's physical page numbers."""
    with zipfile.ZipFile(path) as archive:
        if Path(path).suffix.lower() == ".docx":
            blocks = docx_blocks(archive)
        else:
            blocks = []
            names = sorted(n for n in archive.namelist() if n.startswith("Contents/section") and n.endswith(".xml"))
            for name in names:
                root = xml_part(archive, name)
                for paragraph in root.iter():
                    if paragraph.tag.rsplit("}", 1)[-1] == "p":
                        if any(p is not paragraph and p.tag.rsplit("}", 1)[-1] == "p" for p in paragraph.iter()):
                            continue  # Container paragraphs around tables must not repeat all cell text.
                        text = "".join(t.text or "" for t in paragraph.iter() if t.tag.rsplit("}", 1)[-1] == "t")
                        if text.strip():
                            blocks.append(text.strip())
    units, current = [], ""
    for block in blocks:
        if current and len(current) + len(block) > 6000:
            units.append(current)
            current = ""
        current += ("\n" if current else "") + block
    if current:
        units.append(current)
    if not units:
        raise ValueError("읽을 수 있는 본문이 없습니다. 이미지/보호 문서인지 확인해 주세요.")
    return {"pages": units, "text_kind": "section", "reader_version": READER_VERSION}


def converter(suffix=""):
    if os.name == "nt" and suffix not in {".hwp", ".hwpx"}:
        import winreg
        for flag in (winreg.KEY_READ, winreg.KEY_READ | winreg.KEY_WOW64_32KEY, winreg.KEY_READ | winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID", 0, flag):
                    return "Microsoft Word", "powershell.exe"
            except OSError:
                pass
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if not executable and os.name == "nt":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")):
            candidate = Path(base or "") / "LibreOffice/program/soffice.exe"
            if candidate.is_file():
                executable = str(candidate)
                break
    if executable:
        return "LibreOffice", executable
    if suffix in {".hwp", ".hwpx"}:
        raise ValueError("한글 원문 그림 보기/HWP 읽기에는 LibreOffice 또는 PDF로 내보낸 사본이 필요합니다. HWPX 본문 검색은 직접 사용할 수 있습니다.")
    raise ValueError("원문 그림 보기와 DOC/HWP 읽기에는 Microsoft Word(Windows) 또는 LibreOffice가 필요합니다. DOCX 본문 검색은 변환 없이 사용할 수 있습니다.")


def preview(path, cache_dir):
    path = Path(path).resolve(strict=True)
    renderer, executable = converter(path.suffix.lower())
    signature = fingerprint(path)
    key = hashlib.sha256(("office-preview-1:" + renderer + ":" + signature + path.suffix.lower()).encode()).hexdigest()
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / (key + ".pdf")
    with PREVIEW_LOCK:
        if not target.is_file() or target.stat().st_size < 5:
            with tempfile.TemporaryDirectory(prefix="render-", dir=cache_dir) as directory:
                folder = Path(directory)
                source = folder / ("source" + path.suffix.lower())
                shutil.copyfile(path, source)  # Converter only sees a copy; original is never opened for editing.
                result = folder / "source.pdf"
                if renderer == "Microsoft Word":
                    script = Path(__file__).with_name("word-preview.ps1")
                    # Paths travel in environment values, never interpolated PowerShell code.
                    env = os.environ.copy()
                    env["INSURANCE_WORD_INPUT"] = str(source)
                    env["INSURANCE_WORD_OUTPUT"] = str(result)
                    command = [executable, "-NoProfile", "-NonInteractive", "-Command", script.read_text(encoding="utf-8-sig")]
                    subprocess.run(command, env=env, check=True, capture_output=True, timeout=180)
                else:
                    profile = (folder / "profile").as_uri()
                    subprocess.run([executable, "-env:UserInstallation=" + profile, "--headless", "--convert-to", "pdf:writer_pdf_Export", "--outdir", str(folder), str(source)],
                                   check=True, capture_output=True, timeout=180)
                if not result.is_file() or not result.read_bytes().startswith(b"%PDF-"):
                    raise ValueError("미리보기 PDF를 만들지 못했습니다. 문서 프로그램 설치와 파일의 열기/보호 상태를 확인해 주세요.")
                if fingerprint(path) != signature:
                    raise ValueError("미리보기 생성 중 원본이 변경됐습니다. 새로고침한 뒤 다시 시도하세요.")
                result.replace(target)
    return {"key": key, "fingerprint": signature, "renderer": renderer, "path": target}
