"""Validate the actual public artifact, local links, samples and protected POC content."""
import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for name in ("href", "src"):
            if attrs.get(name):
                self.links.append(attrs[name])


def check(output):
    output = Path(output).resolve()
    metadata = json.loads((output / "publication.json").read_text())
    base = metadata["base_url"]
    for name, digest in metadata["files"].items():
        path = output / name
        assert path.is_file(), "missing published file: " + name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, "artifact mismatch: " + name
    assert (output / "index.html").read_bytes() == (ROOT / "index.html").read_bytes(), "existing landing page changed"
    assert (output / "demo/index.html").is_file()
    assert (output / "demo/lib/pdf.worker.min.js").is_file()
    assert (output / "demo/main-logic.txt").is_file()
    source = (ROOT / "education/index.html").read_bytes().decode("utf-8")
    published = (output / "poc/index.html").read_bytes().decode("utf-8")
    for pattern in (r"<img\b[^>]*>", r"<style\b[^>]*>.*?</style\s*>", r"<script\b[^>]*>.*?</script\s*>"):
        assert re.findall(pattern, source, re.S | re.I) == re.findall(pattern, published, re.S | re.I), "protected POC content changed"
    protected = json.loads((ROOT / "education/protected-assets.json").read_text())
    patterns = {"images": r"<img\b[^>]*>", "styles": r"<style\b[^>]*>.*?</style\s*>", "scripts": r"<script\b[^>]*>.*?</script\s*>"}
    for name, pattern in patterns.items():
        items = re.findall(pattern, source, re.S | re.I)
        assert len(items) == protected[name]["count"], "protected content count changed: " + name
        assert hashlib.sha256("\0".join(items).encode()).hexdigest() == protected[name]["sha256"], "protected content was changed: " + name
    assert "claude.ai/artifact/" not in published, "old demo link remains"
    assert metadata["demo_url"] in published
    assert metadata["commit"][:7] in published
    assert "<!-- publication-version -->" not in published

    data = (output / "demo/data.js").read_text()
    samples = json.loads(re.search(r"window\.SAMPLE_FILES\s*=\s*(\[.*?\]);", data, re.S).group(1))
    assert samples and len(samples) == metadata["sample_pdfs"]
    for name in samples:
        path = output / "demo" / name
        assert path.is_file() and path.read_bytes().startswith(b"%PDF-"), "invalid sample PDF: " + name

    configured = json.loads((ROOT / "site.json").read_text())["base_url"]
    # The unrelated legacy landing page is preserved byte-for-byte above.
    # Validate the newly managed report/demo links without rewriting that site.
    for file in (output / "demo/index.html", output / "poc/index.html"):
        document = file.read_text()
        parser = Links()
        parser.feed(document)
        current = base + file.relative_to(output).as_posix()
        for link in parser.links:
            if link.startswith(("data:", "javascript:", "mailto:", "tel:", "#")):
                continue
            url = urljoin(current, link)
            if not url.startswith(base):
                continue
            suffix = unquote(urlsplit(url[len(base):]).path)
            target = (output / suffix).resolve()
            assert target.is_relative_to(output), "link escapes artifact: " + link
            if target.is_dir():
                target /= "index.html"
            assert target.is_file(), "broken local link: " + str(file.relative_to(output)) + " -> " + link
        if base != configured:
            assert configured not in document, "custom Pages URL was not applied"
    for path in output.rglob("*"):
        if not path.is_file():
            continue
        parts = path.relative_to(output).parts
        assert not any(p in {".git", ".env", ".docs-cache", "node_modules", "product-documents", "docs-folder.txt", "download_log.csv", "server.js", "serve.py"} for p in parts), "private/runtime file in public artifact: " + str(path)
        assert path.suffix != ".py", "server Python file in public artifact"
        if path.suffix == ".pdf":
            assert parts[:2] == ("demo", "sample-기초서류폴더"), "non-sample PDF in public artifact"
    print(f"PASS: {len(metadata['files'])} public files, {len(samples)} valid sample PDFs, links, original landing page, POC images/styles/scripts and publication version")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default=str(ROOT / "_site"))
    check(parser.parse_args().output)
