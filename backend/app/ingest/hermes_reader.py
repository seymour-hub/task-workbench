"""Read-only access to the Hermes state database.

The workbench must never write to Hermes. We open the source SQLite file in
read-only URI mode, enable ``query_only`` and keep every query short so WAL
checkpointing is not blocked.
"""
from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .. import config

BUSY_TIMEOUT_MS = 5000
MAX_RETRIES = 4


class HermesDatabaseError(RuntimeError):
    pass


def _connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise HermesDatabaseError(f"Hermes state.db not found: {path}")
    uri = f"file:{path.as_posix()}?mode=ro"
    connection = sqlite3.connect(
        uri,
        uri=True,
        timeout=BUSY_TIMEOUT_MS / 1000,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    return connection


def _with_retry(action):
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return action()
        except sqlite3.OperationalError as exc:  # locked / busy
            last_error = exc
            time.sleep(0.25 * (attempt + 1))
    raise HermesDatabaseError(f"Hermes database unavailable: {last_error}")


class HermesReader:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config.HERMES_DB

    def _run(self, fn):
        return _with_retry(fn)

    def schema_fingerprint(self) -> dict[str, list[str]]:
        def read() -> dict[str, list[str]]:
            with _connect(self.path) as conn:
                tables = [
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    )
                ]
                result: dict[str, list[str]] = {}
                for table in tables:
                    if table.startswith("sqlite_"):
                        continue
                    result[table] = [
                        row[1] for row in conn.execute(f"PRAGMA table_info({table})")
                    ]
                return result

        return self._run(read)

    def max_message_id(self) -> int:
        def read() -> int:
            with _connect(self.path) as conn:
                row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()
                return int(row[0])

        return self._run(read)

    def first_message_id_since(self, since: float) -> int:
        def read() -> int:
            with _connect(self.path) as conn:
                row = conn.execute(
                    "SELECT COALESCE(MIN(id), 0) FROM messages WHERE timestamp >= ?",
                    (since,),
                ).fetchone()
                return int(row[0])

        return self._run(read)

    def count_messages(self) -> int:
        def read() -> int:
            with _connect(self.path) as conn:
                return int(conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0])

        return self._run(read)

    def iter_sessions(self) -> Iterator[dict[str, Any]]:
        def read() -> list[dict[str, Any]]:
            with _connect(self.path) as conn:
                rows = conn.execute("SELECT * FROM sessions").fetchall()
                return [dict(row) for row in rows]

        for row in self._run(read):
            yield row

    def iter_messages(
        self, after_id: int, limit: int = 500, until_id: int | None = None
    ) -> Iterator[dict[str, Any]]:
        def read() -> list[dict[str, Any]]:
            with _connect(self.path) as conn:
                if until_id is None:
                    rows = conn.execute(
                        "SELECT * FROM messages WHERE id > ? ORDER BY id ASC LIMIT ?",
                        (after_id, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM messages WHERE id > ? AND id <= ? "
                        "ORDER BY id ASC LIMIT ?",
                        (after_id, until_id, limit),
                    ).fetchall()
                return [dict(row) for row in rows]

        for row in self._run(read):
            yield row

    def messages_for_range(
        self, session_id: str, start_id: int, end_id: int
    ) -> list[dict[str, Any]]:
        def read() -> list[dict[str, Any]]:
            with _connect(self.path) as conn:
                rows = conn.execute(
                    "SELECT * FROM messages WHERE session_id = ? AND id >= ? AND id <= ? "
                    "ORDER BY id ASC",
                    (session_id, start_id, end_id),
                ).fetchall()
                return [dict(row) for row in rows]

        return self._run(read)

    def messages_by_ids(self, message_ids: list[int]) -> dict[int, dict[str, Any]]:
        if not message_ids:
            return {}
        placeholders = ",".join("?" for _ in message_ids)
        def read() -> list[dict[str, Any]]:
            with _connect(self.path) as conn:
                rows = conn.execute(
                    f"SELECT * FROM messages WHERE id IN ({placeholders})",
                    tuple(message_ids),
                ).fetchall()
                return [dict(row) for row in rows]

        return {int(row["id"]): row for row in self._run(read)}
