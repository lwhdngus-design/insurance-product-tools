"""Build the public POC and demo from one checkout, without third-party packages."""
import argparse
import hashlib
import html
import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MARKER = ".insurance-product-tools-site"
PUBLIC_SUFFIXES = {".html", ".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".ico"}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args]).decode().strip()


def build(output, base_url=None):
    config = json.loads((ROOT / "site.json").read_text())
    base = (base_url or config["base_url"]).rstrip("/") + "/"
    parsed = urlsplit(base)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("base URL must be an HTTP(S) origin/path without query or fragment")
    output = Path(output).resolve()
    # Only our marked output directory may be replaced. Never remove source/user files.
    if output == ROOT or output in ROOT.parents or output.is_relative_to(ROOT / "product-search") or output.is_relative_to(ROOT / "education"):
        raise ValueError("output would overwrite source files")
    if output.exists() and any(output.iterdir()) and not (output / MARKER).is_file():
        raise ValueError("refusing to replace a nonempty, unmarked directory")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / MARKER).write_text("generated; safe to rebuild\n")

    files = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"]).decode().split("\0")
    copied = []
    for name in filter(None, files):
        relative = Path(name)
        destination = None
        if name == "index.html" or name.startswith("images/"):
            destination = output / relative  # Preserve the existing public landing page.
        elif relative.parts[0] == "product-search":
            tail = Path(*relative.parts[1:])
            if tail.parts[0] in {"tests", ".docs-cache"} or any(p.startswith(".") for p in tail.parts):
                continue
            sample = tail.parts[0] == "sample-기초서류폴더" and tail.suffix == ".pdf"
            csv = tail.parts[0] == "dummy-data" and tail.suffix == ".csv"
            if sample or csv or tail.suffix in PUBLIC_SUFFIXES or str(tail) in {"main-logic.txt", "lib/pdfjs-LICENSE"}:
                destination = output / "demo" / tail
        if destination is None:
            continue
        source = ROOT / relative
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise ValueError("refusing to publish a symlink: " + name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.suffix == ".html":
            data = source.read_bytes().decode("utf-8").replace(config["base_url"], base)
            destination.write_bytes(data.encode("utf-8"))
        else:
            shutil.copyfile(source, destination)
        copied.append(destination.relative_to(output).as_posix())

    education = (ROOT / "education/index.html").read_bytes().decode("utf-8").replace(config["base_url"], base)
    commit = git("rev-parse", "HEAD")
    commit_url = "https://github.com/" + config["repository"] + "/commit/" + commit
    badge = '<span>게시 버전: <a href="' + html.escape(commit_url, quote=True) + '">' + commit[:7] + "</a> · 앱·교육자료·웹 데모 동일 소스</span>"
    if education.count("<!-- publication-version -->") != 1:
        raise ValueError("education publication marker is missing or duplicated")
    education = education.replace("<!-- publication-version -->", badge)
    (output / "poc").mkdir()
    (output / "poc/index.html").write_bytes(education.encode("utf-8"))
    copied.append("poc/index.html")
    (output / ".nojekyll").write_text("")
    metadata = {
        "repository": config["repository"], "branch": config["branch"], "commit": commit,
        "base_url": base, "education_url": base + "poc/", "demo_url": base + "demo/",
        "sample_pdfs": len(list((output / "demo/sample-기초서류폴더").rglob("*.pdf"))),
        "files": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in sorted(copied)},
    }
    (output / "publication.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(f"Built {len(copied)} public files, {metadata['sample_pdfs']} sample PDFs: {output}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "_site"))
    parser.add_argument("--base-url")
    args = parser.parse_args()
    build(args.output, args.base_url)
