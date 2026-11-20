# Working on Insurance Product Tools

Use the existing isolated checkout. Do not create a Git worktree unless the user asks.

## Sources and the release branch

- `product-search/`: the Windows/local app and browser demo source.
- `hanalife-docs/`: Hanalife document downloader.
- `education/index.html`: the complete company POC report, including embedded images.
- `site.json`: canonical repository, release branch and public site base URL.
- Release branch: `main`. Keep it consistent with `update.bat` and the publication workflow. The previous `claude/excel-2an-sheet-format-svwm4c` branch is retained as an upgrade bridge; use `main` for subsequent work.

## Keep the three user deliverables aligned

When a user-visible app change affects installation, features, controls, paths, links or examples, update the corresponding POC report wording and app training instructions in the same task and commit. Publication automatically builds the saved report; it does not invent new prose or screenshots. Do not claim otherwise.

Preserve all existing base64 images, complete `<img>` tags, CSS/style blocks and scripts in the POC report unless the user explicitly requests their modification. Do not reformat or serialize the whole report. Historical screenshot/test records must remain identified as historical; never substitute current results into old screenshots.

Never publish real company PDFs, `product-documents/`, download logs, tokens, `.env`, `.docs-cache`, or `docs-folder.txt`. The build uses tracked files and an explicit public-file selection; only educational PDFs under `product-search/sample-기초서류폴더/` may be published.

## Build, validate and publish

Run `python3 scripts/build_site.py` and `python3 scripts/check_site.py` from this checkout. `_site/` is generated and ignored. Only edit source files. Also run browser checks appropriate to changed behavior; use a non-loopback test hostname for static-demo mode, since loopback URLs select the local Python-server mode. Do not provide localhost preview links to the user.

Before pushing app-code changes, verify the affected workflow. When the question/search engine changes, use the existing 1,000-question bank and check the actual result file, because the legacy runner does not itself fail on mismatches. Do not add unrelated tests for wording-only edits.

Push ordinary commits to the configured release branch without force. GitHub Actions builds the report and demo together and deploys them to `/poc/` and `/demo/`; the original root landing page and images are retained. Inspect the Actions run and check the live `publication.json` commit before claiming publication is complete. A successful push is not proof of deployment.

The PC is updated when the user runs root `update.bat` or `product-search/update.bat` with Internet access. It is not remotely changed by a Git push. Preserve existing user files, PDF folders, SQLite cache and CSV download log. Windows batch execution cannot be claimed verified by Linux-only checks.

Do not update or delete existing Claude artifact pages; those are independent copies and are no longer the canonical published report/demo for this workflow.
