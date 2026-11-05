from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
OUT = SRC / "release"
NAME = "task-workbench-1.0.0"
DST = OUT / NAME
ZIP = OUT / f"{NAME}.zip"

IGNORE_DIRS = {
    ".venv", "node_modules", "dist", "__pycache__", ".pytest_cache",
    "data", "release", "private", "workbench.egg-info", ".git", ".idea", ".vscode",
}
IGNORE_FILES = {"build-release.py"}
IGNORE_SUFFIX = {".pyc", ".pyo", ".log", ".db", ".db-wal", ".db-shm"}


def copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for entry in src.iterdir():
        if entry.name in IGNORE_DIRS or entry.name in IGNORE_FILES:
            continue
        if entry.name.startswith("screenshots"):
            continue
        target = dst / entry.name
        if entry.is_dir():
            copy_tree(entry, target)
        elif entry.suffix.lower() not in IGNORE_SUFFIX:
            shutil.copy2(entry, target)


def replace(path: Path, pairs: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in pairs:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


if DST.exists():
    shutil.rmtree(DST)
DST.mkdir(parents=True)

for name in ("README.md", "LICENSE", ".gitignore", "assets", "backend", "scripts", "web"):
    source = SRC / name
    target = DST / name
    if source.is_dir():
        copy_tree(source, target)
    else:
        shutil.copy2(source, target)

# Publish under the public project name.
replace(
    DST / "backend/pyproject.toml",
    [
        ('name = "workbench"', 'name = "task-workbench"'),
        ('version = "0.1.0"', 'version = "1.0.0"'),
        (
            'description = "Personal task workbench fed by Hermes conversations"',
            'description = "Local task workbench fed by Hermes and Feishu conversations"',
        ),
    ],
)
replace(
    DST / "web/package.json",
    [
        ('"name": "workbench-web"', '"name": "task-workbench-web"'),
        ('"version": "0.1.0"', '"version": "1.0.0"'),
    ],
)

if ZIP.exists():
    ZIP.unlink()
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(DST.rglob("*")):
        if path.is_file():
            archive.write(path, arcname=str(Path(NAME) / path.relative_to(DST)))

print("built", DST)
print("zip", ZIP, round(ZIP.stat().st_size / 1024 / 1024, 2), "MB")
