from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Member, Project


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(Member(name="我", avatar_color="#5B7CFA", role="本人", is_me=True))
    session.add(Project(name="日常工作", color="#5B7CFA"))
    session.commit()
    yield session
    session.close()


def make_source_db(path: Path, message_count: int = 6) -> Path:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            chat_id TEXT,
            chat_type TEXT,
            title TEXT,
            started_at REAL,
            ended_at REAL,
            message_count INTEGER,
            cwd TEXT,
            last_activity_at REAL,
            archived INTEGER DEFAULT 0
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            session_id TEXT,
            role TEXT,
            content TEXT,
            tool_call_id TEXT,
            tool_calls TEXT,
            tool_name TEXT,
            timestamp REAL,
            token_count INTEGER,
            finish_reason TEXT,
            reasoning TEXT
        );
        """
    )
    now = time.time()
    connection.execute(
        "INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "session-1",
            "feishu",
            "oc_test",
            "dm",
            "测试会话",
            now - 3600,
            now,
            message_count,
            None,
            now,
            0,
        ),
    )
    roles = ["user", "assistant", "tool"]
    for index in range(message_count):
        role = roles[index % len(roles)]
        content = f"消息 {index}：整理项目材料并输出纪要"
        if index == 2:
            content = "MEDIA:F:\\outputs\\report.pdf\n" + content
        connection.execute(
            "INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (?,?,?,?,?)",
            (100 + index, "session-1", role, content, now - 3600 + index * 60),
        )
    connection.commit()
    connection.close()
    return path
