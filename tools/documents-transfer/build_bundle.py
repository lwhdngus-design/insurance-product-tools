"""Build the small public tool ZIP; no documents, logs or personal paths."""
import importlib.util
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    spec = importlib.util.spec_from_file_location("documents_transfer", HERE / "documents_transfer.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    (HERE / "1_pack_490MB.bat").write_bytes(tool.make_bat())
    output = ROOT / "downloads" / "documents-transfer-500MB.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ("1_pack_490MB.bat", "documents_transfer.py", "README.txt"):
            archive.write(HERE / name, "documents-transfer-500MB/" + name)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == 3
    print(f"Built and checked: {output} ({output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
