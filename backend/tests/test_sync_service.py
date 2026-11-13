from sqlalchemy import func, select

from app.ingest import sync_service
from app.ingest.hermes_reader import HermesReader
from app.models import MessageCache, Segment
from conftest import make_source_db


def test_sync_is_idempotent(db, tmp_path, monkeypatch):
    source = make_source_db(tmp_path / "state.db")
    monkeypatch.setattr(
        sync_service,
        "HermesReader",
        lambda: HermesReader(source),
    )

    first = sync_service.sync_now(db)
    assert first["ok"] is True
    assert first["new_messages"] == 6
    assert first["cursor"] == 105
    assert db.scalar(select(func.count(MessageCache.id))) == 6
    assert db.scalar(select(func.count(Segment.id))) == 1

    second = sync_service.sync_now(db)
    assert second["ok"] is True
    assert second["new_messages"] == 0
    assert db.scalar(select(func.count(MessageCache.id))) == 6


def test_sync_handles_missing_source(db, monkeypatch, tmp_path):
    missing = tmp_path / "missing.db"
    monkeypatch.setattr(
        sync_service,
        "HermesReader",
        lambda: HermesReader(missing),
    )
    result = sync_service.sync_now(db)
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_replayed_messages_are_dropped(db):
    db.add(
        MessageCache(
            hermes_message_id=1,
            session_id="session-x",
            role="user",
            content="同一段内容",
            content_hash="hash-x",
            timestamp=100.0,
        )
    )
    db.commit()

    payloads = [
        {"session_id": "session-x", "role": "user", "content_hash": "hash-x", "timestamp": 100.0},
        {"session_id": "session-x", "role": "user", "content_hash": "hash-x", "timestamp": 101.0},
        {"session_id": "session-x", "role": "user", "content_hash": "hash-y", "timestamp": 100.0},
    ]
    kept = sync_service.drop_replayed_messages(db, payloads)

    assert len(kept) == 2
    assert [item["content_hash"] for item in kept] == ["hash-x", "hash-y"]
