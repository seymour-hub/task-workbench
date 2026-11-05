from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..models import Deliverable, DeliverableRoot, FileIndex, Task
from ..schemas import FileRootCreate
from .deliverable_rules import (
    classify_deliverable,
    file_timestamp,
    is_final_by_name,
    logical_group,
    version_label,
)

IGNORED_NAMES = {
    "node_modules", ".git", ".svn", ".hg", ".venv", "venv", "env", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".idea", ".vscode", ".next", "dist", "build",
    "$RECYCLE.BIN", "System Volume Information", "Tencent Files",
    "BaiduNetdiskTmp", "OneNote 笔记本", "archive", "backup", "backups",
}
IGNORED_FILES = {"desktop.ini", "thumbs.db", ".ds_store"}


def _is_hidden(name: str) -> bool:
    return name.startswith(".") or name.lower() in IGNORED_FILES


def _ext_list(root: DeliverableRoot) -> list[str]:
    return [ext.lower() for ext in (root.include_ext or config.DEFAULT_INCLUDE_EXT)]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _iter_files(root_path: Path, depth: int, extensions: list[str], max_files: int):
    base_depth = len(root_path.parts)
    seen = 0
    stack: list[Path] = [root_path]
    while stack:
        current = stack.pop()
        if len(current.parts) - base_depth >= depth:
            continue
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name.lower() in {name.lower() for name in IGNORED_NAMES}:
                                continue
                            if _is_hidden(entry.name):
                                continue
                            stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        if _is_hidden(entry.name):
                            continue
                        suffix = Path(entry.name).suffix.lower()
                        if extensions and suffix not in extensions:
                            continue
                        stat = entry.stat(follow_symlinks=False)
                        seen += 1
                        yield Path(entry.path), stat.st_size, stat.st_mtime
                        if seen >= max_files:
                            return
                    except OSError:
                        continue
        except OSError:
            continue


def scan_root(db: Session, root: DeliverableRoot, max_files: int = 20_000) -> dict[str, Any]:
    root_path = Path(root.path)
    started = time.time()
    result = {
        "root_id": root.id,
        "label": root.label,
        "ok": False,
        "scanned": 0,
        "inserted": 0,
        "updated": 0,
        "missing": 0,
        "truncated": False,
        "error": None,
    }
    if not root_path.exists() or not root_path.is_dir():
        result["error"] = f"path not found: {root.path}"
        root.last_scan_at = started
        db.flush()
        return result

    existing = {
        row.path: row
        for row in db.scalars(select(FileIndex).where(FileIndex.root_id == root.id))
    }
    seen_paths: set[str] = set()
    extensions = _ext_list(root)

    try:
        for path, size, mtime in _iter_files(root_path, max(1, root.depth), extensions, max_files):
            absolute = str(path)
            seen_paths.add(absolute)
            row = existing.get(absolute)
            if row is None:
                row = FileIndex(
                    root_id=root.id,
                    path=absolute,
                    relative_path=str(path.relative_to(root_path)),
                    name=path.name,
                    ext=path.suffix.lower(),
                    size=size,
                    mtime=mtime,
                    exists_flag=True,
                )
                db.add(row)
                existing[absolute] = row
                result["inserted"] += 1
            else:
                changed = row.size != size or abs((row.mtime or 0) - mtime) > 1
                row.size = size
                row.mtime = mtime
                row.exists_flag = True
                row.last_seen_at = started
                if changed:
                    row.content_hash = None
                    result["updated"] += 1
            result["scanned"] += 1
        result["truncated"] = result["scanned"] >= max_files

        for path, row in existing.items():
            if path not in seen_paths and row.exists_flag:
                row.exists_flag = False
                result["missing"] += 1

        root.last_scan_at = started
        root.file_count = result["scanned"]
        result["ok"] = True
        db.flush()
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        db.rollback()
        raise
    result["duration_ms"] = int((time.time() - started) * 1000)
    return result


def scan_all(db: Session, max_files: int = 20_000) -> list[dict[str, Any]]:
    results = []
    roots = list(db.scalars(select(DeliverableRoot).where(DeliverableRoot.enabled.is_(True))))
    for root in roots:
        try:
            results.append(scan_root(db, root, max_files=max_files))
        except Exception as exc:  # noqa: BLE001
            results.append(
                {"root_id": root.id, "label": root.label, "ok": False, "error": str(exc)}
            )
    return results


def create_root(db: Session, data: FileRootCreate) -> DeliverableRoot:
    path = Path(data.path)
    if not path.exists() or not path.is_dir():
        raise ValueError(f"目录不存在: {data.path}")
    root = DeliverableRoot(
        label=data.label,
        path=str(path),
        enabled=data.enabled,
        depth=data.depth,
        include_ext=data.include_ext or config.DEFAULT_INCLUDE_EXT,
        exclude_globs=data.exclude_globs or config.DEFAULT_EXCLUDE_GLOBS,
        auto_attach=data.auto_attach,
        scan_interval_min=data.scan_interval_min,
    )
    db.add(root)
    db.flush()
    return root


def file_to_dict(row: FileIndex) -> dict[str, Any]:
    return {
        "id": row.id,
        "root_id": row.root_id,
        "path": row.path,
        "relative_path": row.relative_path,
        "name": row.name,
        "ext": row.ext,
        "size": row.size,
        "mtime": row.mtime,
        "exists_flag": row.exists_flag,
        "ignored": row.ignored,
        "indexed_at": row.indexed_at,
        "last_seen_at": row.last_seen_at,
    }


def attach_file(db: Session, file: FileIndex, task_id: int) -> Deliverable:
    task = db.get(Task, task_id)
    if not task:
        raise ValueError("任务不存在")
    existing = db.scalar(
        select(Deliverable).where(
            Deliverable.task_id == task_id,
            Deliverable.file_id == file.id,
        )
    )
    if existing:
        return existing
    classification = classify_deliverable(file.path, file.name)
    group_key, logical_name = logical_group(file.name, file.path)
    version_at = file_timestamp(file.path, file.mtime)
    intermediate = bool(classification["is_intermediate"])
    item = Deliverable(
        task_id=task_id,
        file_id=file.id,
        title=file.name,
        type=_deliverable_type(file.ext),
        path_or_url=file.path,
        file_size=file.size,
        exists_flag=file.exists_flag,
        attach_mode="manual",
        group_key=group_key,
        logical_name=logical_name,
        version_label=version_label(file.path, file.name, version_at),
        version_at=version_at,
        is_final=classification["ok"]
        and not intermediate
        and is_final_by_name(file.name, file.path),
        is_intermediate=intermediate,
    )
    db.add(item)
    db.flush()
    return item


def _deliverable_type(ext: str) -> str:
    ext = (ext or "").lower()
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}:
        return "image"
    if ext in {".mp4", ".mov", ".avi", ".mkv"}:
        return "video"
    if ext in {".doc", ".docx", ".pdf", ".md", ".txt"}:
        return "doc"
    return "file"


def reveal(path: str) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        raise ValueError("文件或目录不存在")
    roots = config_root_paths()
    if not any(_is_within(target, root) for root in roots):
        raise PermissionError("该路径不在已配置的交付物根目录内")
    if os.name == "nt":
        subprocess.Popen(["explorer", "/select,", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target.parent)])
    return {"ok": True}


def _open_windows(path: str) -> None:
    """Open with the default app and try to bring its window to the foreground."""
    escaped = path.replace("'", "''")
    script = (
        f"$p = Start-Process -FilePath '{escaped}' -PassThru; "
        "Start-Sleep -Milliseconds 700; "
        "$ws = New-Object -ComObject WScript.Shell; "
        "try { $ws.AppActivate($p.Id) | Out-Null } catch {}"
    )
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-Command",
                script,
            ],
            capture_output=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode == 0:
            return
    except (OSError, subprocess.SubprocessError):
        pass
    os.startfile(path)  # type: ignore[attr-defined]


def open_file(path: str) -> dict[str, Any]:
    """Open a deliverable with the system default application."""
    if path.startswith(("http://", "https://")):
        if not webbrowser.open(path):
            raise RuntimeError("无法打开链接")
        return {"ok": True, "mode": "url"}

    target = Path(path)
    if not target.exists():
        raise ValueError("文件或目录不存在")
    if os.name == "nt":
        _open_windows(str(target))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])
    return {"ok": True, "mode": "file"}


def config_root_paths() -> list[Path]:
    from ..db import SessionLocal

    with SessionLocal() as db:
        return [
            Path(root.path)
            for root in db.scalars(
                select(DeliverableRoot).where(DeliverableRoot.enabled.is_(True))
            )
        ]


def index_referenced_path(
    db: Session, path: str, task_id: int | None, message_id: int | None = None
) -> Deliverable | None:
    if not path or not os.path.isabs(path) or not os.path.exists(path):
        return None
    normalized = os.path.normcase(os.path.normpath(path))
    file_row = None
    for row in db.scalars(select(FileIndex).limit(20_000)):
        if os.path.normcase(os.path.normpath(row.path)) == normalized:
            file_row = row
            break
    existing = None
    if file_row:
        existing = db.scalar(
            select(Deliverable).where(
                Deliverable.task_id == task_id,
                Deliverable.file_id == file_row.id,
            )
        )
    if existing:
        return existing
    item = Deliverable(
        task_id=task_id,
        file_id=file_row.id if file_row else None,
        title=Path(path).name,
        type=_deliverable_type(Path(path).suffix),
        path_or_url=path,
        file_size=Path(path).stat().st_size if Path(path).is_file() else None,
        exists_flag=True,
        attach_mode="auto_referenced",
        confidence=0.9,
        source_message_id=message_id,
    )
    db.add(item)
    db.flush()
    return item
