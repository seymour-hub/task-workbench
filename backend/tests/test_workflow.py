import time

from app.models import (
    Deliverable,
    InboxItem,
    Issue,
    MessageCache,
    PendingConfirmation,
    Segment,
    SessionCache,
    SyncState,
    Task,
)
from app.services import confirmation_service, intent_service
from app.services.intent_service import heuristic_intent
from app.services.task_link_service import link_segment


def test_heuristic_start_and_complete():
    intent, title, confidence = heuristic_intent("开始任务：产品演示视频 v3.1")
    assert intent == "start_task"
    assert "产品演示" in (title or "")
    assert confidence == 1.0

    intent, title, _ = heuristic_intent("产品演示视频 v3.1完成了")
    assert intent == "complete_task"
    assert "产品演示" in (title or "")

    intent, _, _ = heuristic_intent("今天天气不错")
    assert intent == "none"


def _confirmation(db, kind, payload):
    confirmation = PendingConfirmation(
        code="A1234",
        kind=kind,
        payload=payload,
        status="pending",
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )
    db.add(confirmation)
    db.commit()
    return confirmation


def test_start_confirmation_creates_task_and_auto_inbox(db, monkeypatch):
    monkeypatch.setattr(confirmation_service, "send_text", lambda *args, **kwargs: None)
    confirmation = _confirmation(
        db,
        "start_task",
        {
            "title": "产品演示视频 v3.1",
            "chat_id": "chat-1",
            "session_id": "session-1",
            "message_ids": [101],
            "started_at": time.time() - 60,
        },
    )
    result = confirmation_service.resolve_confirmation(db, confirmation, "加入")
    assert result["action"] == "created"
    task = db.query(Task).one()
    assert task.status == "in_progress"
    assert task.auto_created is True
    assert task.code == "T0001"
    assert task.chat_id == "chat-1"
    inbox = db.query(InboxItem).filter(InboxItem.status == "auto_accepted").one()
    assert inbox.payload["task_id"] == task.id


def test_complete_confirmation_marks_final_and_closes_task(db, monkeypatch):
    monkeypatch.setattr(confirmation_service, "send_text", lambda *args, **kwargs: None)
    task = Task(
        title="产品演示视频 v3.1",
        status="in_progress",
        chat_id="chat-1",
        started_at=time.time() - 3600,
    )
    db.add(task)
    db.commit()
    older = Deliverable(
        task_id=task.id,
        title="v1",
        path_or_url=r"F:\outputs\video_v1.mp4",
        group_key="video",
        version_at=time.time() - 100,
        is_final=True,
    )
    newer = Deliverable(
        task_id=task.id,
        title="v2",
        path_or_url=r"F:\outputs\video_v2.mp4",
        group_key="video",
        version_at=time.time(),
        is_final=False,
    )
    db.add_all([older, newer])
    db.commit()
    confirmation = _confirmation(
        db,
        "complete_task",
        {"task_id": task.id, "title": task.title, "completed_at": time.time()},
    )
    result = confirmation_service.resolve_confirmation(
        db, confirmation, "完成，最终版是 video_v2.mp4"
    )
    assert result["action"] == "completed"
    db.refresh(task)
    assert task.status == "done"
    assert task.ended_at is not None
    db.refresh(newer)
    db.refresh(older)
    assert newer.is_final is True
    assert older.is_final is False


def test_intent_confirmation_roundtrip(db, monkeypatch):
    monkeypatch.setattr(intent_service, "send_text", lambda *args, **kwargs: None)
    monkeypatch.setattr(confirmation_service, "send_text", lambda *args, **kwargs: None)
    monkeypatch.setattr(intent_service.config, "get_secret", lambda name: None)

    now = time.time()
    db.add(
        SessionCache(
            id="session-1",
            source="feishu",
            chat_id="chat-1",
            chat_type="dm",
            title="测试会话",
            message_count=4,
            last_activity_at=now,
        )
    )
    db.add(SyncState(key="intent_cursor.message_id", value="0"))
    db.add(SyncState(key="confirm_cursor.message_id", value="0"))
    db.add(
        MessageCache(
            hermes_message_id=1,
            session_id="session-1",
            role="user",
            content="开始任务：测试视频",
            timestamp=now,
        )
    )
    db.add(
        Segment(
            session_id="session-1",
            start_message_id=1,
            end_message_id=1,
            started_at=now,
            ended_at=now,
            message_count=1,
            content_hash="seg-1",
            extract_status="pending",
        )
    )
    db.commit()

    intent_service.scan_intents(db)
    confirmation = db.query(PendingConfirmation).filter_by(kind="start_task").one()

    db.add(
        MessageCache(
            hermes_message_id=2,
            session_id="session-1",
            role="user",
            content="加入",
            timestamp=now + 1,
        )
    )
    db.commit()
    confirmation_service.scan_replies(db)
    task = db.query(Task).one()
    assert task.status == "in_progress"
    assert confirmation.status == "confirmed"

    db.add(
        MessageCache(
            hermes_message_id=3,
            session_id="session-1",
            role="user",
            content="测试视频完成了",
            timestamp=now + 2,
        )
    )
    db.commit()
    intent_service.scan_intents(db)
    complete = db.query(PendingConfirmation).filter_by(kind="complete_task").one()

    db.add(
        MessageCache(
            hermes_message_id=4,
            session_id="session-1",
            role="user",
            content="完成",
            timestamp=now + 3,
        )
    )
    db.commit()
    confirmation_service.scan_replies(db)
    db.refresh(task)
    db.refresh(complete)
    assert task.status == "done"
    assert task.ended_at is not None


def test_apply_extraction_to_linked_task(db):
    from app.ai.extractor import _apply_to_task
    from app.schemas import (
        AIDecision,
        AIDeliverable,
        AIIssue,
        AIMilestone,
        AITask,
        ExtractionResult,
    )

    task = Task(
        title="产品演示视频 v3.1",
        status="in_progress",
        chat_id="chat-1",
        started_at=time.time(),
    )
    segment = Segment(
        session_id="session-1",
        start_message_id=1,
        end_message_id=5,
        started_at=time.time(),
        ended_at=time.time(),
        message_count=5,
        content_hash="abc",
        extract_status="pending",
        task_id=None,
    )
    db.add(task)
    db.commit()
    segment.task_id = task.id
    db.add(segment)
    db.commit()

    result = ExtractionResult(
        tasks=[AITask(title="不应新建的任务", evidence_message_ids=[1])],
        issues=[AIIssue(title="测试问题", evidence_message_ids=[1])],
        deliverables=[
            AIDeliverable(
                title="测试图",
                type="image",
                path_or_url=r"D:\hermes\outputs\documents\test.png",
                is_final=True,
                evidence_message_ids=[1],
            )
        ],
        decisions=[AIDecision(summary="测试决策", evidence_message_ids=[1])],
        next_steps=[],
        milestones=[AIMilestone(summary="阶段一完成", evidence_message_ids=[1])],
    )
    counts = _apply_to_task(db, task, result, segment)
    db.flush()
    assert counts["issues"] == 1
    assert counts["deliverables"] == 1
    assert counts["notes"] == 1
    assert counts["milestones"] == 1
    assert db.query(Task).count() == 1
    assert db.query(Issue).count() == 1
    assert db.query(Deliverable).count() == 1


def test_link_segment_to_active_task(db):
    task = Task(
        title="产品演示视频 v3.1",
        status="in_progress",
        chat_id="chat-1",
        started_at=time.time(),
    )
    segment = Segment(
        session_id="session-1",
        start_message_id=1,
        end_message_id=5,
        started_at=time.time(),
        ended_at=time.time(),
        message_count=5,
        content_hash="abc",
        extract_status="pending",
    )
    db.add_all([task, segment])
    db.commit()
    link_segment(db, segment, task, method="single_active")
    db.refresh(segment)
    assert segment.task_id == task.id
    assert segment.link_method == "single_active"
