"""Rules that decide what counts as a deliverable and how versions group.

The workbench must not treat build scripts, scratch HTML or temporary audio as
deliverables. A deliverable is a user-facing output that a person could open,
review or publish.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

OUTPUT_EXT = {
    ".mp4", ".mov", ".mkv", ".avi",
    ".html", ".htm",
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".md", ".txt", ".zip", ".7z",
}

EXCLUDED_DIR_PARTS = {
    "cache", "scratch", "tmp", "temp", "build", "dist", "node_modules",
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache", "logs", "log",
    "backup", "backups", "archive", "scripts", "health-check",
}

EXCLUDED_EXT = {
    ".py", ".pyc", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue",
    ".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1", ".psm1",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".log", ".tmp", ".lock", ".db", ".sqlite", ".sqlite3", ".sql", ".map",
    ".css", ".scss", ".less", ".java", ".c", ".cc", ".cpp", ".h", ".hpp",
    ".go", ".rs", ".php", ".rb", ".wav", ".flac", ".aac", ".m4a",
    ".woff", ".woff2", ".ttf", ".ico",
}

EXCLUDED_TITLE_KEYWORDS = (
    "脚本", "生成器", "补丁", "源码", "scratch",
    "中间产物", "中间文件", "watchdog", "register_ensure", "重启网关",
)

INTERMEDIATE_KEYWORDS = (
    "样片", "sample", "草稿", "draft", "临时", "temp", "tmp", "scratch",
    "中间", "过程", "预览", "preview", "wip", "测试版", "beta",
)

FINAL_KEYWORDS = ("成片", "最终", "final", "release", "交付版", "定稿")

VERSION_TOKEN_RE = re.compile(r"\bv?\d+(?:\.\d+){1,3}\b", re.IGNORECASE)
DATE_RE = re.compile(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})")
QUALITY_RE = re.compile(
    r"\b(?:1080p|720p|4k|2160p|25fps|30fps|60fps|\d+min|\d+秒|\d+s|\d+帧|\d+(?:\.\d+)?mb)\b",
    re.IGNORECASE,
)
FORMAT_WORDS = (
    "mp4", "html", "pdf", "png", "jpg", "jpeg", "mov", "zip", "docx", "pptx", "xlsx",
    "交互版", "单文件", "离线", "可播", "双版本", "成片", "最终版", "交付版",
    "1080p", "4min", "6000帧",
)
PAREN_RE = re.compile(r"[（(【\[].*?[）)】\]]")


def normalize_path(path: str) -> str:
    return (path or "").replace("/", "\\")


def path_parts(path: str) -> list[str]:
    return [part.lower() for part in normalize_path(path).split("\\") if part]


def _title_key(title: str) -> str:
    return (title or "").lower()


def classify_deliverable(path: str, title: str = "") -> dict[str, Any]:
    """Return whether the file is a user-facing deliverable.

    ``ok=False`` means scripts, caches, configs and temporary artifacts.
    ``is_intermediate=True`` means it is a legitimate output but not a final
    version (e.g. a 24-second sample or a draft).
    """
    normalized = normalize_path(path)
    parts = path_parts(normalized)
    lower_title = _title_key(title)
    ext = Path(normalized).suffix.lower()

    if not normalized:
        return {"ok": False, "reason": "空路径", "is_intermediate": True, "ext": ext}

    if ext in EXCLUDED_EXT:
        return {"ok": False, "reason": f"过程/代码文件 {ext}", "is_intermediate": True, "ext": ext}
    if ext not in OUTPUT_EXT:
        return {"ok": False, "reason": f"非交付物格式 {ext or '无扩展名'}", "is_intermediate": True, "ext": ext}

    joined_parts = set(parts[:-1])
    for part in EXCLUDED_DIR_PARTS:
        if part in joined_parts:
            return {
                "ok": False,
                "reason": f"位于过程目录 {part}",
                "is_intermediate": True,
                "ext": ext,
            }

    haystack = f"{lower_title} {normalized.lower()}"
    for keyword in EXCLUDED_TITLE_KEYWORDS:
        if keyword.lower() in haystack:
            return {
                "ok": False,
                "reason": f"命中过程关键词 {keyword}",
                "is_intermediate": True,
                "ext": ext,
            }

    is_intermediate = any(keyword in haystack for keyword in INTERMEDIATE_KEYWORDS)
    return {
        "ok": True,
        "reason": "过程版本" if is_intermediate else "交付物",
        "is_intermediate": is_intermediate,
        "ext": ext,
    }


def clean_title(title: str) -> str:
    text = PAREN_RE.sub(" ", title or "")
    text = re.sub(r"[_\-]+", " ", text)
    for word in FORMAT_WORDS:
        text = re.sub(re.escape(word), " ", text, flags=re.IGNORECASE)
    text = VERSION_TOKEN_RE.sub(" ", text)
    text = DATE_RE.sub(" ", text)
    text = QUALITY_RE.sub(" ", text)
    text = re.sub(
        r"(?:最终版|交付版|交互版|正式版|完整版|高清版|单文件版|版本|版)\s*$",
        " ",
        text,
    )
    text = re.sub(r"\s+", " ", text).strip(" ·-—")
    return text


def logical_group(title: str, path: str, hint: str | None = None) -> tuple[str, str]:
    """Return (group_key, display_name) for version grouping.

    File stems are usually generated consistently (same base name for every
    export format), so they are preferred over free-form titles.
    """
    stem = Path(normalize_path(path)).stem
    if hint and hint.strip():
        display = hint.strip()
    else:
        display = clean_title(stem)
        if len(display) < 2:
            display = clean_title(title) or stem or title
    key = re.sub(r"[\s\W_]+", "", display.lower(), flags=re.UNICODE)[:160]
    return key or "other", display[:200]


def version_label(path: str, title: str = "", timestamp: float | None = None) -> str:
    normalized = normalize_path(path)
    stem = Path(normalized).stem
    ext = Path(normalized).suffix.upper().lstrip(".")
    version = ""
    match = VERSION_TOKEN_RE.search(stem) or VERSION_TOKEN_RE.search(title or "")
    if match:
        version = match.group(0)
    date_match = DATE_RE.search(stem)
    date_text = ""
    if date_match:
        date_text = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
    elif timestamp:
        date_text = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
    pieces = [piece for piece in (version, date_text, ext) if piece]
    return " · ".join(pieces) or ext or "版本"


def file_timestamp(path: str, fallback: float | None = None) -> float:
    try:
        if os.path.exists(path):
            return os.path.getmtime(path)
    except OSError:
        pass
    return float(fallback or 0)


def is_final_by_name(title: str, path: str) -> bool:
    haystack = f"{title or ''} {normalize_path(path)}".lower()
    return any(keyword in haystack for keyword in FINAL_KEYWORDS)
