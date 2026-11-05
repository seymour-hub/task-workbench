from __future__ import annotations

import logging
import re
import time

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..ai.deduper import normalize_title
from ..models import (
    Deliverable,
    InboxItem,
    Member,
    MessageCache,
    PendingConfirmation,
    Project,
    Segment,
    SessionCache,
    SyncState,
    Task,
    TaskEvent,
)
from .notify_service import send_text
from .task_link_service import (
    apply_pending_inbox_to_task,
    chat_id_for_session,
    link_segment,
    link_unlinked_segments,
)

logger = logging.getLogger(__name__)

CODE_RE = re.compile(r"#?\s*(A[A-F0-9]{4})\b", re.IGNORECASE)
NO_WORDS = ("不用", "不要", "不加入", "忽略", "取消", "算了", "否", "不是", "先不", "不")
YES_WORDS = (
    "加入", "加", "好", "可以", "是", "确认", "要", "添加", "建",
    "完成", "已完成", "结束", "搞定", "行", "没问题", "ok", "okay",
)


def _ensure_cursor(db: Session, key: str) -> int:
    row = db.get(SyncState, key)
    if row is None:
        max_id = db.scalar(select(func.max(MessageCache.hermes_message_id))) or 0
        db.add(SyncState(key=key, value=str(max_id)))
        db.flush()
        return int(max_id)
    try:
        return int(row.value or 0)
    except (TypeError, ValueError):
        return 0


def _set_cursor(db: Session, key: str, value: int) -> None:
    row = db.get(SyncState, key)
    if row is None:
        db.add(SyncState(key=key, value=str(value)))
    else:
        row.value = str(value)
    db.flush()


START_YES = ("加入", "好", "可以", "确认", "是", "要", "添加", "建", "没问题", "ok", "行")
START_NO = ("不用", "不要", "不加入", "忽略", "取消", "算了", "先不")
COMPLETE_YES = ("完成", "已完成", "确认", "结束", "搞定", "好", "可以", "是", "交付", "ok", "行")
COMPLETE_NO = ("取消", "不用", "不要", "未完成", "还没", "先不")


def _decision_of(text: str, kind: str) -> str | None:
    """Only treat short, clearly-affirmative replies as decisions."""
    clean = _strip_code(text).strip().lower().lstrip("，,。.!！ ")
    if not clean:
        return None
    yes_words = START_YES if kind == "start_task" else COMPLETE_YES
    no_words = START_NO if kind == "start_task" else COMPLETE_NO
    if any(clean.startswith(word) for word in no_words):
        return "no"
    if any(clean.startswith(word) for word in yes_words):
        return "yes"
    if len(clean) <= 16:
        if any(word in clean for word in no_words):
            return "no"
        if any(word in clean for word in yes_words):
            return "yes"
    return None


def _strip_code(text: str) -> str:
    return CODE_RE.sub("", text).strip()


def _segment_for_message(
    db: Session, session_id: str, message_id: int
) -> Segment | None:
    return db.scalar(
        select(Segment)
        .where(
            Segment.session_id == session_id,
            Segment.start_message_id <= message_id,
            Segment.end_message_id >= message_id,
        )
        .limit(1)
    )


def _mark_segment_linked(db: Session, task: Task, session_id: str, message_id: int) -> None:
    segment = _segment_for_message(db, session_id, message_id)
    if not segment:
        return
    if segment.task_id is None:
        link_segment(db, segment, task, method="explicit_start", confidence=1.0)
        return
    # The segment starts with this task's "start" message. Before the task
    # existed it may have been tentatively linked to another active task; move
    # it here. Never steal a segment a human linked manually.
    if (
        segment.task_id != task.id
        and segment.start_message_id >= message_id
        and segment.link_method in (None, "single_active", "similarity")
    ):
        link_segment(db, segment, task, method="explicit_start", confidence=1.0)
        return
    apply_pending_inbox_to_task(db, task, segment.id)


def _create_task_from_start(db: Session, confirmation: PendingConfirmation) -> Task:
    payload = confirmation.payload or {}
    title = str(payload.get("title") or "未命名任务").strip()[:300]
    me = db.scalar(select(Member).where(Member.is_me.is_(True)).limit(1))
    other = db.scalar(select(Project).where(Project.name == "其他"))
    task = Task(
        title=title,
        description=f"从飞书对话自动创建。\n\n{payload.get('source_excerpt') or ''}"[:4000],
        status="in_progress",
        priority="medium",
        project_id=other.id if other else None,
        assignee_id=me.id if me else None,
        category="其他",
        source_type="feishu_intent",
        source_session_id=payload.get("session_id"),
        chat_id=payload.get("chat_id"),
        source_message_ids=payload.get("message_ids") or [],
        source_excerpt=payload.get("source_excerpt"),
        ai_confidence=float(payload.get("confidence") or 0.8),
        fingerprint=normalize_title(title),
        started_at=float(payload.get("started_at") or time.time()),
        created_at=float(payload.get("started_at") or time.time()),
        sort_order=time.time() * 1000,
        auto_created=True,
    )
    db.add(task)
    db.flush()
    task.code = f"T{task.id:04d}"
    db.add(
        TaskEvent(
            task_id=task.id,
            type="created",
            to_value="in_progress",
            note="飞书确认加入工作台",
            actor="ai",
        )
    )
    db.flush()

    # Link the source segment and any already-extracted candidates.
    for message_id in payload.get("message_ids") or []:
        _mark_segment_linked(db, task, str(payload.get("session_id") or ""), int(message_id))

    segment = _segment_for_message(
        db, str(payload.get("session_id") or ""), int((payload.get("message_ids") or [0])[0])
    )
    pending_tasks = list(
        db.scalars(
            select(InboxItem).where(
                InboxItem.kind == "task",
                InboxItem.status == "pending",
                InboxItem.segment_id == segment.id,
            )
        )
    ) if segment else []
    for item in pending_tasks:
        item.status = "accepted"
        item.reviewed_at = time.time()
        item.payload = {**(item.payload or {}), "task_id": task.id, "code": task.code}

    db.add(
        InboxItem(
            kind="task",
            payload={
                "title": task.title,
                "task_id": task.id,
                "code": task.code,
                "source": "feishu_confirm",
                "auto_created": True,
            },
            confidence=1.0,
            status="auto_accepted",
            segment_id=segment.id if segment else None,
            source_message_ids=payload.get("message_ids") or [],
            reviewed_at=time.time(),
        )
    )
    db.flush()
    send_text(
        db,
        f"✅ 已加入工作台\n{task.code}《{task.title}》\n后续进展会自动累积到这个任务。",
        kind="task_confirm",
        title="任务已加入",
    )
    return task


def _mark_final_versions(db: Session, task: Task, hint: str) -> int:
    items = list(db.scalars(select(Deliverable).where(Deliverable.task_id == task.id)))
    if not items:
        return 0
    groups: dict[tuple[str, str], list[Deliverable]] = {}
    for item in items:
        ext = item.path_or_url.rsplit(".", 1)[-1].lower() if "." in item.path_or_url else ""
        groups.setdefault((item.group_key or "other", ext), []).append(item)
    hint_lower = (hint or "").lower()

    def matches(item: Deliverable) -> bool:
        name = item.path_or_url.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        return bool(
            (name and name in hint_lower)
            or (item.title and item.title.lower() in hint_lower)
        )

    marked = 0
    for rows in groups.values():
        explicit = [item for item in rows if matches(item)]
        if explicit:
            for item in rows:
                item.is_final = item in explicit
                if item in explicit:
                    item.is_intermediate = False
            marked += len(explicit)
            continue
        if any(item.is_final for item in rows):
            marked += sum(1 for item in rows if item.is_final)
            continue
        rows.sort(key=lambda item: item.version_at or item.created_at)
        candidates = [item for item in rows if not item.is_intermediate] or rows
        candidates[-1].is_final = True
        candidates[-1].is_intermediate = False
        marked += 1
    db.flush()
    return marked


def _complete_task(db: Session, confirmation: PendingConfirmation, hint: str) -> Task:
    payload = confirmation.payload or {}
    task = db.get(Task, int(payload.get("task_id") or 0))
    if not task:
        raise ValueError("任务不存在")
    ended_at = float(payload.get("completed_at") or time.time())
    task.status = "done"
    task.ended_at = ended_at
    task.completed_at = ended_at
    task.progress = 100
    db.add(
        TaskEvent(
            task_id=task.id,
            type="status_changed",
            from_value="in_progress",
            to_value="done",
            note="飞书确认完成",
            actor="ai",
        )
    )
    db.add(
        TaskEvent(
            task_id=task.id,
            type="milestone_end",
            note="任务结束",
            actor="ai",
            created_at=ended_at,
        )
    )
    marked = _mark_final_versions(db, task, hint)
    db.flush()
    send_text(
        db,
        f"✅ 已完成《{task.title}》\n结束时间：{time.strftime('%Y-%m-%d %H:%M', time.localtime(ended_at))}\n"
        f"已标记 {marked} 个最终版文件。",
        kind="task_confirm",
        title="任务已完成",
    )
    return task


def resolve_confirmation(
    db: Session,
    confirmation: PendingConfirmation,
    text: str,
    decision: str | None = None,
) -> dict[str, object]:
    clean = _strip_code(text).lower()
    payload = confirmation.payload or {}
    decision = decision or _decision_of(text, confirmation.kind)
    if confirmation.kind == "start_task":
        if decision != "yes":
            confirmation.status = "rejected"
            confirmation.resolved_at = time.time()
            confirmation.reply_text = text[:500]
            db.add(
                InboxItem(
                    kind="task",
                    payload={
                        "title": payload.get("title") or "未命名任务",
                        "source": "feishu_confirm",
                        "reject_reason": "飞书回复未加入",
                    },
                    confidence=0.5,
                    status="rejected",
                    source_message_ids=payload.get("message_ids") or [],
                    reviewed_at=time.time(),
                )
            )
            db.flush()
            send_text(
                db,
                f"已忽略《{payload.get('title') or '任务'}》。",
                kind="task_confirm",
                title="已忽略任务",
            )
            return {"ok": True, "action": "rejected"}
        task = _create_task_from_start(db, confirmation)
        confirmation.status = "confirmed"
        confirmation.resolved_at = time.time()
        confirmation.reply_text = text[:500]
        db.flush()
        link_unlinked_segments(db)
        return {"ok": True, "action": "created", "task_id": task.id, "code": task.code}

    if confirmation.kind == "complete_task":
        if decision != "yes":
            confirmation.status = "rejected"
            confirmation.resolved_at = time.time()
            confirmation.reply_text = text[:500]
            db.flush()
            send_text(
                db,
                f"已取消完成任务《{payload.get('title') or ''}》。",
                kind="task_confirm",
                title="已取消完成",
            )
            return {"ok": True, "action": "cancelled"}
        task = _complete_task(db, confirmation, text)
        confirmation.status = "confirmed"
        confirmation.resolved_at = time.time()
        confirmation.reply_text = text[:500]
        db.flush()
        return {"ok": True, "action": "completed", "task_id": task.id}

    confirmation.status = "rejected"
    confirmation.resolved_at = time.time()
    confirmation.reply_text = text[:500]
    db.flush()
    return {"ok": True, "action": "ignored"}


def scan_replies(
    db: Session, *, limit: int = 30, since: float | None = None
) -> dict[str, int]:
    cursor = _ensure_cursor(db, "confirm_cursor.message_id")
    now = time.time()
    # A process can die between claiming a confirmation and creating its task;
    # requeue claims older than 5 minutes so they can be retried.
    for stale in db.scalars(
        select(PendingConfirmation).where(
            PendingConfirmation.status == "resolving",
            PendingConfirmation.resolved_at.is_not(None),
            PendingConfirmation.resolved_at < now - 300,
        )
    ):
        stale.status = "pending"
        stale.resolved_at = None
    db.flush()
    pending = list(
        db.scalars(
            select(PendingConfirmation)
            .where(
                PendingConfirmation.status == "pending",
                PendingConfirmation.expires_at > now,
            )
            .order_by(PendingConfirmation.created_at.asc())
        )
    )
    for expired in db.scalars(
        select(PendingConfirmation).where(
            PendingConfirmation.status == "pending",
            PendingConfirmation.expires_at <= now,
        )
    ):
        expired.status = "expired"
    db.flush()

    statement = (
        select(MessageCache)
        .join(SessionCache, SessionCache.id == MessageCache.session_id)
        .where(
            MessageCache.role == "user",
            SessionCache.source == "feishu",
        )
        .order_by(MessageCache.hermes_message_id.asc())
    )
    if since is not None:
        statement = statement.where(MessageCache.timestamp >= since).limit(300)
    else:
        statement = statement.where(MessageCache.hermes_message_id > cursor).limit(limit)
    messages = list(db.scalars(statement))
    if not messages:
        return {"checked": 0, "resolved": 0}

    resolved = 0
    max_seen = cursor
    for message in messages:
        max_seen = max(max_seen, message.hermes_message_id)
        if not pending:
            continue
        text = (message.content or "").strip()
        if not text:
            continue
        message_chat = chat_id_for_session(db, message.session_id)
        same_chat = [
            item
            for item in pending
            if (
                not (item.payload or {}).get("chat_id")
                or (item.payload or {}).get("chat_id") == message_chat
            )
            and item.created_at <= (message.timestamp or now) + 5
        ]
        if not same_chat:
            continue
        code_match = CODE_RE.search(text)
        target: PendingConfirmation | None = None
        decision: str | None = None
        if code_match:
            code = code_match.group(1).upper()
            target = next((item for item in same_chat if item.code == code), None)
            if target is None:
                send_text(
                    db,
                    f"编号 #{code} 不存在或已过期，请重新确认。",
                    kind="task_confirm",
                    title="确认编号无效",
                )
                continue
            decision = _decision_of(text, target.kind) or "yes"
        elif len(same_chat) == 1 and _decision_of(text, same_chat[0].kind):
            target = same_chat[0]
            decision = _decision_of(text, target.kind)
        else:
            if not any(_decision_of(text, item.kind) for item in same_chat):
                continue
            matches = [
                item
                for item in same_chat
                if str((item.payload or {}).get("title") or "") in text
            ]
            if len(matches) == 1:
                target = matches[0]
                decision = _decision_of(text, target.kind)
            if target is None:
                codes = "、".join(f"#{item.code}" for item in same_chat[:5])
                send_text(
                    db,
                    f"当前有多条待确认，请带编号回复：{codes}",
                    kind="task_confirm",
                    title="待确认任务",
                )
                continue
        target_id = target.id
        try:
            # Atomically claim the confirmation. Two concurrent workflow runs
            # (scheduler + "检查新任务") otherwise both create a task for the
            # same reply. The claim is committed before creating the task.
            claimed = db.execute(
                update(PendingConfirmation)
                .where(
                    PendingConfirmation.id == target_id,
                    PendingConfirmation.status == "pending",
                )
                .values(status="resolving", resolved_at=time.time())
            )
            db.commit()
            if claimed.rowcount != 1:
                pending = [item for item in pending if item.id != target_id]
                continue
            db.refresh(target)
            resolve_confirmation(db, target, text, decision)
            db.commit()
            resolved += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            stuck = db.get(PendingConfirmation, target_id)
            if stuck is not None and stuck.status == "resolving":
                stuck.status = "pending"
                stuck.resolved_at = None
                db.commit()
            logger.exception("resolve confirmation failed: %s", exc)
        pending = [item for item in pending if item.id != target_id]

    if max_seen > cursor:
        _set_cursor(db, "confirm_cursor.message_id", max_seen)
    return {"checked": len(messages), "resolved": resolved}
