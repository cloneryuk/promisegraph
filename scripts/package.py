"""Build a source ZIP with an explicit allowlist, excluding local secrets and caches."""

import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = {"app", "data", "docs", "eval", "tests", "scripts", ".github"}
FILES = {
    ".env.example",
    ".gitignore",
    "requirements.txt",
    "requirements-lock.txt",
    "pyproject.toml",
    "README.md",
    "compose.yaml",
    "start.ps1",
    "start.sh",
}
SKIP = {"__pycache__", ".pytest_cache", ".venv", "runtime", "runs"}


def package(target):
    target = target.resolve()
    if ROOT == target or ROOT in target.parents:
        raise ValueError("Write the ZIP outside the project folder.")
    selected = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP for part in relative.parts):
            continue
        if relative.name == ".env" or relative.suffix in (".pyc", ".zip"):
            continue
        if relative.parts[0] in FOLDERS or str(relative) in FILES:
            selected.append((path, relative))
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, relative in selected:
            archive.write(path, "promisegraph/" + relative.as_posix())
    with zipfile.ZipFile(target) as archive:
        assert not any(
            Path(n).name == ".env" or "__pycache__" in n for n in archive.namelist()
        )
        assert archive.testzip() is None
    print(f"{len(selected)} source/artifact files; local .env excluded.")
    print("SHA256 " + hashlib.sha256(target.read_bytes()).hexdigest())
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    package(parser.parse_args().out)
