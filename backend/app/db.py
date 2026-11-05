from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker

from . import config
from .models import (
    Base,
    DeliverableRoot,
    Member,
    Project,
    Setting,
    Task,
)

engine = create_engine(
    f"sqlite:///{config.DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False, "timeout": 15},
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


DEFAULT_SETTINGS: dict[str, str] = {
    "ui.display_name": "我",
    "ui.timezone": config.DEFAULT_TIMEZONE,
    "work.start": "09:00",
    "work.end": "18:00",
    "sync.enabled": "true",
    "sync.interval_sec": "60",
    "sync.backfill_days": "90",
    "extract.enabled": "true",
    "extract.sources": "feishu",
    "extract.window_days": "14",
    "extract.daily_token_budget": "1000000",
    "extract.auto_accept_threshold": "0",
    "ai.base_url": config.DEFAULT_DEEPSEEK_BASE_URL,
    "ai.model": config.DEFAULT_DEEPSEEK_MODEL,
    "ai.enabled": "true",
    "notify.enabled": "true",
    "notify.target": "",
    "notify.digest_time": "09:00",
    "notify.due_time": "09:05",
    "notify.overdue_time": "18:00",
    "notify.weekly_time": "18:00",
    "notify.weekly_day": "4",
    "files.scan_interval_min": "30",
    "files.max_files_per_root": "20000",
}


def get_setting(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.get(Setting, key)
    if row and row.value is not None:
        return row.value
    return default if default is not None else DEFAULT_SETTINGS.get(key)


def set_setting(db: Session, key: str, value: str | None) -> None:
    row = db.get(Setting, key)
    if row is None:
        row = Setting(key=key, value=value)
        db.add(row)
    else:
        row.value = value


def get_bool_setting(db: Session, key: str, default: bool = False) -> bool:
    value = get_setting(db, key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_setting(db: Session, key: str, default: int = 0) -> int:
    value = get_setting(db, key)
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def get_float_setting(db: Session, key: str, default: float = 0.0) -> float:
    value = get_setting(db, key)
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _ensure_sqlite_columns() -> None:
    """Lightweight forward migration for the local single-user database."""
    wanted = {
        "tasks": {
            "category": "VARCHAR(80)",
            "subcategory": "VARCHAR(80)",
            "work_types": "JSON",
            "started_at": "FLOAT",
            "ended_at": "FLOAT",
            "chat_id": "VARCHAR(160)",
            "code": "VARCHAR(40)",
            "auto_created": "BOOLEAN DEFAULT 0",
        },
        "segments": {
            "task_id": "INTEGER",
            "link_method": "VARCHAR(40)",
            "link_confidence": "FLOAT",
        },
        "deliverables": {
            "group_key": "VARCHAR(200)",
            "logical_name": "VARCHAR(300)",
            "version_label": "VARCHAR(120)",
            "version_at": "FLOAT",
            "is_final": "BOOLEAN DEFAULT 0",
            "is_intermediate": "BOOLEAN DEFAULT 0",
        },
    }
    with engine.begin() as connection:
        for table, columns in wanted.items():
            existing = {
                row[1]
                for row in connection.execute(text(f"PRAGMA table_info({table})"))
            }
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                    )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_deliverables_group_key "
                "ON deliverables (group_key)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_deliverables_is_final "
                "ON deliverables (is_final)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tasks_category "
                "ON tasks (category)"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tasks_subcategory "
                "ON tasks (subcategory)"
            )
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_tasks_chat_id ON tasks (chat_id)")
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_segments_task_id "
                "ON segments (task_id)"
            )
        )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()
    with session_scope() as db:
        for key, value in DEFAULT_SETTINGS.items():
            if db.get(Setting, key) is None:
                db.add(Setting(key=key, value=value))
        db.flush()

        if db.scalar(select(Member).limit(1)) is None:
            db.add(Member(name="我", avatar_color="#5B7CFA", role="本人", is_me=True))
        db.flush()
        me = db.scalar(select(Member).where(Member.is_me.is_(True)).limit(1))
        if me is not None:
            db.query(Task).filter(Task.assignee_id.is_(None)).update(
                {"assignee_id": me.id}, synchronize_session=False
            )
        db.query(Task).filter(Task.auto_created.is_(None)).update(
            {"auto_created": False}, synchronize_session=False
        )

        if db.scalar(select(Project).limit(1)) is None:
            db.add(
                Project(
                    name="日常工作",
                    description="未归类的日常工作",
                    color="#5B7CFA",
                )
            )

        if db.scalar(select(DeliverableRoot).limit(1)) is None:
            for item in config.DEFAULT_DELIVERABLE_ROOTS:
                db.add(
                    DeliverableRoot(
                        label=item["label"],
                        path=item["path"],
                        enabled=item.get("enabled", True),
                        depth=item.get("depth", 4),
                        include_ext=config.DEFAULT_INCLUDE_EXT,
                        exclude_globs=config.DEFAULT_EXCLUDE_GLOBS,
                        auto_attach=True,
                    )
                )

        target = get_setting(db, "notify.target") or ""
        if not target:
            detected = config.detect_feishu_target()
            if detected:
                set_setting(db, "notify.target", detected)


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)
