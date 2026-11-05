#!/usr/bin/env python3
"""Block commits that contain personal data, secrets or local runtime files.

Run manually with `python scripts/check-privacy.py`, or install the local hook:

    .git/hooks/pre-commit  ->  exec python scripts/check-privacy.py

Extra terms can be listed one per line in data/privacy-blacklist.txt
(gitignored), for example company names or personal project names.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLACKLIST = ROOT / "data" / "privacy-blacklist.txt"
SKIP_PARTS = {
    ".git", ".venv", "node_modules", "dist", "__pycache__",
    ".pytest_cache", "data", "release", "backups",
    "screenshots", "workbench.egg-info",
}
SKIP_SUFFIX = {".db", ".db-wal", ".db-shm", ".log", ".pyc", ".pyo", ".ico", ".jpg", ".jpeg", ".png", ".gif", ".mp4", ".zip", ".7z"}

USERNAME = Path.home().name
BUILTIN = [
    (r"\boc_[a-f0-9]{16,}\b", "Feishu chat_id"),
    (r"\bsk-[A-Za-z0-9]{20,}\b", "API key"),
    (r"\bcli_[A-Za-z0-9]{16,}\b", "Feishu app credential"),
    (rf"(?i)C:\\+Users\\+{re.escape(USERNAME)}", "personal Windows profile path"),
    (rf"(?i)\b{re.escape(USERNAME)}\b", "current Windows username"),
]


def staged_files() -> list[Path] | None:
    try:
        output = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return [ROOT / line for line in output.decode("utf-8", "replace").splitlines() if line.strip()]


def all_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIX:
            continue
        files.append(path)
    return files


def patterns() -> list[tuple[re.Pattern[str], str]]:
    items = [(re.compile(pattern), label) for pattern, label in BUILTIN]
    if BLACKLIST.exists():
        for line in BLACKLIST.read_text(encoding="utf-8", errors="replace").splitlines():
            term = line.strip()
            if term and not term.startswith("#"):
                items.append((re.compile(re.escape(term), re.IGNORECASE), f"blacklist:{term}"))
    return items


def main() -> int:
    files = staged_files()
    if files is None:
        files = all_files()
        scope = "working tree"
    else:
        scope = "staged files"
    checks = patterns()
    findings: list[str] = []

    for path in files:
        try:
            relative = path.relative_to(ROOT)
        except ValueError:
            continue
        if any(part in SKIP_PARTS for part in relative.parts):
            findings.append(f"{relative}: local runtime/private directory")
            continue
        if path.suffix.lower() in SKIP_SUFFIX:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for regex, label in checks:
                if regex.search(line):
                    findings.append(f"{relative}:{line_no}: {label} -> {line.strip()[:120]}")

    if findings:
        print(f"Privacy check failed on {scope}:")
        for item in findings[:50]:
            print("  " + item)
        print(f"\n{len(findings)} finding(s). Fix them before committing.")
        return 1
    print(f"Privacy check passed on {scope} ({len(files)} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
