from __future__ import annotations

import hashlib
import re
from typing import Any

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
MEDIA_RE = re.compile(r"MEDIA:\s*([^\r\n]+)")
WIN_PATH_RE = re.compile(r"([A-Za-z]:\\[^\s`<>|\"*?，。；、）】]+)")
BACKTICK_PATH_RE = re.compile(r"`([A-Za-z]:\\[^`\r\n]+)`")
TRAILING_JUNK = " \t\r\n，。；;、,.)）】]}>'\""

USER_MAX_CHARS = 20_000
ASSISTANT_MAX_CHARS = 20_000
TOOL_MAX_CHARS = 2_000
TOOL_CALLS_MAX_CHARS = 8_000


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = ANSI_RE.sub("", value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    return text.strip()


def truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + "\n…[truncated]", True


def content_hash(text: str, tool_name: str | None = None) -> str:
    payload = f"{tool_name or ''}\x1f{text}".encode("utf-8", errors="replace")
    return hashlib.sha256(payload).hexdigest()


def extract_media_paths(text: str) -> list[str]:
    paths: list[str] = []
    for match in MEDIA_RE.finditer(text or ""):
        raw = match.group(1).strip().strip("`").strip()
        if raw:
            paths.append(raw.rstrip(TRAILING_JUNK).strip())
    return paths


def extract_windows_paths(text: str) -> list[str]:
    found: list[str] = []
    for pattern in (BACKTICK_PATH_RE, WIN_PATH_RE):
        for match in pattern.finditer(text or ""):
            raw = match.group(1).strip().rstrip(TRAILING_JUNK).strip()
            if raw and len(raw) > 3:
                found.append(raw)
    # stable unique
    seen: set[str] = set()
    result: list[str] = []
    for path in found:
        key = path.lower()
        if key not in seen:
            seen.add(key)
            result.append(path)
    return result


def normalize_message(row: dict[str, Any]) -> dict[str, Any] | None:
    role = str(row.get("role") or "")
    if role == "session_meta":
        return None

    content = clean_text(row.get("content"))
    if role == "tool":
        content, truncated = truncate(content, TOOL_MAX_CHARS)
    elif role == "assistant":
        content, truncated = truncate(content, ASSISTANT_MAX_CHARS)
    else:
        content, truncated = truncate(content, USER_MAX_CHARS)

    tool_calls = row.get("tool_calls")
    if isinstance(tool_calls, (dict, list)):
        import json

        tool_calls = json.dumps(tool_calls, ensure_ascii=False)
    tool_calls_text = clean_text(tool_calls) if tool_calls else None
    if tool_calls_text:
        tool_calls_text, _ = truncate(tool_calls_text, TOOL_CALLS_MAX_CHARS)

    return {
        "hermes_message_id": int(row["id"]),
        "session_id": str(row.get("session_id") or ""),
        "role": role,
        "content": content,
        "content_hash": content_hash(content, row.get("tool_name")),
        "tool_name": row.get("tool_name"),
        "tool_calls": tool_calls_text,
        "timestamp": float(row.get("timestamp") or 0),
        "truncated": truncated,
    }


def message_prompt_text(row: Any, max_chars: int = 2_500) -> str:
    """Render one cached message for the extraction prompt."""
    role = getattr(row, "role", "user")
    content = getattr(row, "content", "") or ""
    if len(content) > max_chars:
        content = content[:max_chars] + "…"
    tool = getattr(row, "tool_name", None)
    prefix = f"[{role}]"
    if tool:
        prefix = f"[tool:{tool}]"
    return f"{prefix} #{getattr(row, 'hermes_message_id', '?')}: {content}"
