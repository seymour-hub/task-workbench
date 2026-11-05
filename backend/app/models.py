from __future__ import annotations

import time

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> float:
    return time.time()


class Base(DeclarativeBase):
    pass


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    avatar_color: Mapped[str] = mapped_column(String(20), default="#5B7CFA")
    role: Mapped[str] = mapped_column(String(40), default="成员")
    is_me: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(20), default="#5B7CFA")
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[float] = mapped_column(Float, default=now)
    updated_at: Mapped[float] = mapped_column(Float, default=now, onupdate=now)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="todo", index=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    due_at: Mapped[float | None] = mapped_column(Float, index=True)
    start_at: Mapped[float | None] = mapped_column(Float)
    started_at: Mapped[float | None] = mapped_column(Float, index=True)
    ended_at: Mapped[float | None] = mapped_column(Float, index=True)
    completed_at: Mapped[float | None] = mapped_column(Float)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    source_type: Mapped[str | None] = mapped_column(String(30))
    source_session_id: Mapped[str | None] = mapped_column(String(160))
    chat_id: Mapped[str | None] = mapped_column(String(160), index=True)
    code: Mapped[str | None] = mapped_column(String(40), index=True)
    auto_created: Mapped[bool] = mapped_column(Boolean, default=False)
    source_message_ids: Mapped[list | None] = mapped_column(JSON)
    source_excerpt: Mapped[str | None] = mapped_column(Text)
    ai_confidence: Mapped[float | None] = mapped_column(Float)
    category: Mapped[str | None] = mapped_column(String(80), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(80), index=True)
    work_types: Mapped[list | None] = mapped_column(JSON)
    fingerprint: Mapped[str | None] = mapped_column(String(300), index=True)
    sort_order: Mapped[float] = mapped_column(Float, default=0)
    deleted_at: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    updated_at: Mapped[float] = mapped_column(Float, default=now, onupdate=now)

    __table_args__ = (
        Index("ix_tasks_status_due", "status", "due_at"),
        Index("ix_tasks_project_status", "project_id", "status"),
    )


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    from_value: Mapped[str | None] = mapped_column(String(200))
    to_value: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)
    message_id: Mapped[int | None] = mapped_column(Integer)
    actor: Mapped[str] = mapped_column(String(60), default="me")
    created_at: Mapped[float] = mapped_column(Float, default=now)


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="open")
    resolution: Mapped[str | None] = mapped_column(Text)
    source_message_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    resolved_at: Mapped[float | None] = mapped_column(Float)


class DeliverableRoot(Base):
    __tablename__ = "deliverable_roots"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    path: Mapped[str] = mapped_column(String(500), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    depth: Mapped[int] = mapped_column(Integer, default=4)
    include_ext: Mapped[list | None] = mapped_column(JSON)
    exclude_globs: Mapped[list | None] = mapped_column(JSON)
    auto_attach: Mapped[bool] = mapped_column(Boolean, default=True)
    scan_interval_min: Mapped[int] = mapped_column(Integer, default=30)
    last_scan_at: Mapped[float | None] = mapped_column(Float)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class FileIndex(Base):
    __tablename__ = "file_index"

    id: Mapped[int] = mapped_column(primary_key=True)
    root_id: Mapped[int] = mapped_column(ForeignKey("deliverable_roots.id"), index=True)
    path: Mapped[str] = mapped_column(String(1000))
    relative_path: Mapped[str] = mapped_column(String(1000))
    name: Mapped[str] = mapped_column(String(300), index=True)
    ext: Mapped[str] = mapped_column(String(20), default="", index=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    mtime: Mapped[float] = mapped_column(Float, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(80), index=True)
    exists_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    ignored: Mapped[bool] = mapped_column(Boolean, default=False)
    indexed_at: Mapped[float] = mapped_column(Float, default=now)
    last_seen_at: Mapped[float] = mapped_column(Float, default=now)

    __table_args__ = (UniqueConstraint("root_id", "path", name="uq_file_root_path"),)


class Deliverable(Base):
    __tablename__ = "deliverables"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("file_index.id"))
    title: Mapped[str] = mapped_column(String(300))
    type: Mapped[str] = mapped_column(String(20), default="file")
    path_or_url: Mapped[str] = mapped_column(String(1000))
    file_size: Mapped[int | None] = mapped_column(Integer)
    exists_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    attach_mode: Mapped[str] = mapped_column(String(30), default="manual")
    confidence: Mapped[float | None] = mapped_column(Float)
    source_message_id: Mapped[int | None] = mapped_column(Integer)
    group_key: Mapped[str | None] = mapped_column(String(200), index=True)
    logical_name: Mapped[str | None] = mapped_column(String(300))
    version_label: Mapped[str | None] = mapped_column(String(120))
    version_at: Mapped[float | None] = mapped_column(Float)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_intermediate: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class SessionCache(Base):
    __tablename__ = "sessions_cache"

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    source: Mapped[str | None] = mapped_column(String(40), index=True)
    chat_id: Mapped[str | None] = mapped_column(String(160))
    chat_type: Mapped[str | None] = mapped_column(String(40))
    title: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[float | None] = mapped_column(Float)
    ended_at: Mapped[float | None] = mapped_column(Float)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    cwd: Mapped[str | None] = mapped_column(String(1000))
    last_activity_at: Mapped[float | None] = mapped_column(Float)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    ingested_at: Mapped[float] = mapped_column(Float, default=now)


class MessageCache(Base):
    __tablename__ = "messages_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    hermes_message_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    session_id: Mapped[str] = mapped_column(String(160), index=True)
    role: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(80), default="")
    tool_name: Mapped[str | None] = mapped_column(String(80))
    tool_calls: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[float] = mapped_column(Float, default=0, index=True)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[float] = mapped_column(Float, default=now)

    __table_args__ = (Index("ix_messages_session_ts", "session_id", "timestamp"),)


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(160), index=True)
    start_message_id: Mapped[int] = mapped_column(Integer)
    end_message_id: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[float] = mapped_column(Float, default=0)
    ended_at: Mapped[float] = mapped_column(Float, default=0)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(80), default="")
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    link_method: Mapped[str | None] = mapped_column(String(40))
    link_confidence: Mapped[float | None] = mapped_column(Float)
    extract_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    extract_error: Mapped[str | None] = mapped_column(Text)
    extracted_at: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class InboxItem(Base):
    __tablename__ = "inbox_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    segment_id: Mapped[int | None] = mapped_column(ForeignKey("segments.id"))
    source_message_ids: Mapped[list | None] = mapped_column(JSON)
    dedup_of_task_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    reviewed_at: Mapped[float | None] = mapped_column(Float)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    start_at: Mapped[float] = mapped_column(Float, index=True)
    end_at: Mapped[float | None] = mapped_column(Float)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    location: Mapped[str | None] = mapped_column(String(300))
    color: Mapped[str] = mapped_column(String(20), default="#5B7CFA")
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
    source: Mapped[str] = mapped_column(String(30), default="manual")
    created_at: Mapped[float] = mapped_column(Float, default=now)
    updated_at: Mapped[float] = mapped_column(Float, default=now, onupdate=now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(40), default="feishu")
    kind: Mapped[str] = mapped_column(String(40), default="test")
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    dedup_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[float | None] = mapped_column(Float)
    read_at: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[float] = mapped_column(Float, default=now)


class SyncState(Base):
    __tablename__ = "sync_state"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[float] = mapped_column(Float, default=now, onupdate=now)


class ProcessedIntent(Base):
    __tablename__ = "processed_intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    intent: Mapped[str] = mapped_column(String(40), default="none")
    created_at: Mapped[float] = mapped_column(Float, default=now)


class PendingConfirmation(Base):
    __tablename__ = "pending_confirmations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[float] = mapped_column(Float, default=now)
    expires_at: Mapped[float | None] = mapped_column(Float)
    resolved_at: Mapped[float | None] = mapped_column(Float)
    reply_text: Mapped[str | None] = mapped_column(Text)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[float] = mapped_column(Float, default=now, onupdate=now)
