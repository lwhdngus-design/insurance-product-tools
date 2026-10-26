"""Check the deployed edge content, not just a successful workflow status."""
import argparse
import hashlib
import json
import time
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def fetch(base, name, commit):
    url = base.rstrip("/") + "/" + quote(name, safe="/") + "?revision=" + commit
    with urlopen(Request(url, headers={"Cache-Control": "no-cache"}), timeout=20) as response:
        return response.read()


def check(base, commit):
    for attempt in range(18):
        try:
            metadata = json.loads(fetch(base, "publication.json", commit))
            assert metadata["commit"] == commit, "published commit has not reached the edge yet"
            paths = ["index.html", "poc/index.html", "demo/index.html", "demo/lib/pdf.worker.min.js"]
            paths.append(next(name for name in metadata["files"] if name.endswith(".pdf")))
            for name in paths:
                data = fetch(base, name, commit)
                assert hashlib.sha256(data).hexdigest() == metadata["files"][name], "stale or mismatched public file: " + name
            report = fetch(base, "poc/index.html", commit).decode("utf-8")
            assert "claude.ai/artifact/" not in report
            assert base.rstrip("/") + "/demo/" in report
            print("PASS: public POC, demo, PDF worker, sample PDF and preserved landing page match commit " + commit)
            return
        except (URLError, AssertionError, ValueError, KeyError, StopIteration) as error:
            if attempt == 17:
                raise
            print("Waiting for Pages edge: " + str(error), flush=True)
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    check(args.base_url, args.expected_commit)
