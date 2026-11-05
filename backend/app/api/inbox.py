from __future__ import annotations

import os
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..ai.deduper import similarity
from ..db import get_db
from ..models import (
    Deliverable,
    InboxItem,
    Issue,
    MessageCache,
    PendingConfirmation,
    Project,
    Segment,
    Task,
    TaskEvent,
)
from ..schemas import InboxAccept, InboxReject, TaskCreate
from ..services.deliverable_rules import (
    classify_deliverable,
    file_timestamp,
    is_final_by_name,
    logical_group,
    normalize_path,
    version_label,
)
from ..services.task_service import create_task, serialize_task

router = APIRouter(prefix="/inbox", tags=["inbox"])


def _get_item(db: Session, item_id: int) -> InboxItem:
    item = db.get(InboxItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="收件箱条目不存在")
    return item


def _project_for_hint(db: Session, hint: str | None, explicit: int | None) -> int | None:
    if explicit:
        return explicit
    if not hint:
        return None
    project = db.scalar(
        select(Project).where(func.lower(Project.name) == hint.strip().lower())
    )
    return project.id if project else None


def _excerpt(db: Session, message_ids: list[int] | None) -> str | None:
    if not message_ids:
        return None
    message = db.scalar(
        select(MessageCache)
        .where(MessageCache.hermes_message_id == int(message_ids[0]))
        .limit(1)
    )
    if not message:
        return None
    return (message.content or "")[:500]


def _attach_segment_assets(
    db: Session, item: InboxItem, task: Task
) -> tuple[int, int, int]:
    attached_issues = 0
    attached_deliverables = 0
    attached_notes = 0
    if not item.segment_id:
        return attached_issues, attached_deliverables, attached_notes
    siblings = list(
        db.scalars(
            select(InboxItem).where(
                InboxItem.segment_id == item.segment_id,
                InboxItem.status == "pending",
                InboxItem.kind.in_(["issue", "deliverable", "note"]),
            )
        )
    )
    issue_titles = [
        title
        for title in db.scalars(select(Issue.title).where(Issue.task_id == task.id))
    ]
    note_set = {
        event.note
        for event in db.scalars(
            select(TaskEvent).where(
                TaskEvent.task_id == task.id, TaskEvent.type == "ai_note"
            )
        )
        if event.note
    }

    for sibling in siblings:
        payload = sibling.payload or {}
        if sibling.kind == "issue":
            title = str(payload.get("title") or "未命名问题")[:300]
            if any(similarity(title, existing) >= 85 for existing in issue_titles):
                sibling.status = "accepted"
                sibling.reviewed_at = time.time()
                continue
            db.add(
                Issue(
                    task_id=task.id,
                    title=title,
                    detail=payload.get("detail"),
                    severity=payload.get("severity") or "medium",
                    source_message_id=(sibling.source_message_ids or [None])[0],
                )
            )
            db.add(
                TaskEvent(
                    task_id=task.id,
                    type="issue_added",
                    note=title[:200],
                    actor="ai",
                )
            )
            issue_titles.append(title)
            sibling.status = "accepted"
            sibling.reviewed_at = time.time()
            attached_issues += 1
        elif sibling.kind == "note":
            summary = str(payload.get("summary") or "").strip()
            if not summary:
                sibling.status = "accepted"
                sibling.reviewed_at = time.time()
                continue
            note_text = f"[{payload.get('category') or 'note'}] {summary}"
            if note_text in note_set:
                sibling.status = "accepted"
                sibling.reviewed_at = time.time()
                continue
            db.add(
                TaskEvent(
                    task_id=task.id,
                    type="ai_note",
                    note=note_text,
                    actor="ai",
                )
            )
            note_set.add(note_text)
            sibling.status = "accepted"
            sibling.reviewed_at = time.time()
            attached_notes += 1
        else:
            path = str(payload.get("path_or_url") or "")
            title = str(payload.get("title") or os.path.basename(path))[:300]
            classification = classify_deliverable(path, title)
            if not classification["ok"]:
                sibling.status = "rejected"
                sibling.reviewed_at = time.time()
                sibling.payload = {
                    **payload,
                    "reject_reason": classification["reason"],
                }
                continue
            if db.scalar(
                select(Deliverable).where(
                    Deliverable.task_id == task.id,
                    Deliverable.path_or_url == path,
                )
            ):
                sibling.status = "accepted"
                sibling.reviewed_at = time.time()
                continue
            exists = bool(path and os.path.exists(path))
            group_key, logical_name = logical_group(
                title, path, payload.get("logical_name")
            )
            version_at = payload.get("version_at") or file_timestamp(path)
            intermediate = bool(
                payload.get("is_intermediate", classification["is_intermediate"])
            )
            final = payload.get("is_final")
            if final is None:
                final = is_final_by_name(title, path) and not intermediate
            db.add(
                Deliverable(
                    task_id=task.id,
                    file_id=payload.get("file_id"),
                    title=title,
                    type=payload.get("type") or "file",
                    path_or_url=path,
                    file_size=os.path.getsize(path) if exists and os.path.isfile(path) else None,
                    exists_flag=exists,
                    attach_mode="auto_referenced",
                    confidence=0.8,
                    source_message_id=(sibling.source_message_ids or [None])[0],
                    group_key=group_key,
                    logical_name=logical_name,
                    version_label=payload.get("version")
                    or version_label(path, title, version_at),
                    version_at=version_at,
                    is_final=bool(final),
                    is_intermediate=intermediate,
                )
            )
            db.add(
                TaskEvent(
                    task_id=task.id,
                    type="deliverable_added",
                    note=title[:200],
                )
            )
            sibling.status = "accepted"
            sibling.reviewed_at = time.time()
            attached_deliverables += 1
    if attached_deliverables:
        db.flush()
        from ..services.deliverable_service import recompute_finals

        recompute_finals(db, task.id)
    return attached_issues, attached_deliverables, attached_notes


@router.get("")
def list_inbox(
    status: str = Query(default="pending"),
    kind: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    statement = select(InboxItem).order_by(InboxItem.created_at.desc()).limit(300)
    if status != "all":
        statement = statement.where(InboxItem.status == status)
    if kind:
        statement = statement.where(InboxItem.kind == kind)
    items = list(db.scalars(statement))
    return {
        "items": [
            {
                "id": item.id,
                "kind": item.kind,
                "payload": item.payload,
                "confidence": item.confidence,
                "status": item.status,
                "segment_id": item.segment_id,
                "source_message_ids": item.source_message_ids,
                "dedup_of_task_id": item.dedup_of_task_id,
                "created_at": item.created_at,
                "reviewed_at": item.reviewed_at,
            }
            for item in items
        ],
        "counts": {
            "pending": db.scalar(
                select(func.count(InboxItem.id)).where(InboxItem.status == "pending")
            )
            or 0,
            "duplicate": db.scalar(
                select(func.count(InboxItem.id)).where(InboxItem.status == "duplicate")
            )
            or 0,
        },
        "by_kind": dict(
            db.execute(
                select(InboxItem.kind, func.count(InboxItem.id))
                .where(InboxItem.status == "pending")
                .group_by(InboxItem.kind)
            ).all()
        ),
    }


@router.post("/{item_id}/accept")
def accept_item(
    item_id: int,
    payload: InboxAccept,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    item = _get_item(db, item_id)
    if item.status == "accepted":
        raise HTTPException(status_code=409, detail="该条目已接受")
    if item.status == "duplicate" and not force:
        raise HTTPException(status_code=409, detail="疑似重复任务；如确认请加 force=true")
    data = item.payload or {}

    if item.kind == "task":
        title = (payload.title or data.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="任务标题为空")
        due_at = payload.due_at if payload.due_at is not None else data.get("due_at")
        segment = db.get(Segment, item.segment_id) if item.segment_id else None
        task = create_task(
            db,
            TaskCreate(
                title=title,
                description=payload.description or data.get("description"),
                project_id=_project_for_hint(
                    db, data.get("project_hint"), payload.project_id
                ),
                status=payload.status or data.get("status") or "todo",
                priority=payload.priority or data.get("priority") or "medium",
                due_at=due_at,
                source_type="hermes_session",
            ),
            actor="ai",
            source_event="accepted",
            source_session_id=segment.session_id if segment else None,
            source_message_ids=data.get("evidence_message_ids") or [],
            source_excerpt=_excerpt(db, data.get("evidence_message_ids")),
            ai_confidence=data.get("confidence"),
        )
        # If a Feishu confirmation for the same work is still pending, merge it
        # into this task instead of letting it create a duplicate later.
        for pending in list(
            db.scalars(
                select(PendingConfirmation).where(
                    PendingConfirmation.kind == "start_task",
                    PendingConfirmation.status == "pending",
                )
            )
        ):
            pending_payload = pending.payload or {}
            pending_title = str(pending_payload.get("title") or "")
            pending_chat = pending_payload.get("chat_id")
            if similarity(pending_title, task.title) < 75:
                continue
            if task.chat_id and pending_chat and task.chat_id != pending_chat:
                continue
            pending.status = "confirmed"
            pending.resolved_at = time.time()
            pending.reply_text = f"merged into task #{task.id}"
            pending.payload = {**pending_payload, "merged_task_id": task.id}
            if not task.chat_id and pending_chat:
                task.chat_id = pending_chat
            pending_started = pending_payload.get("started_at")
            if pending_started and (
                not task.started_at or pending_started < task.started_at
            ):
                task.started_at = float(pending_started)
            message_ids = sorted(
                set((task.source_message_ids or []) + (pending_payload.get("message_ids") or []))
            )
            task.source_message_ids = message_ids
            db.add(
                TaskEvent(
                    task_id=task.id,
                    type="merged",
                    note=f"飞书确认 #{pending.code} 合并到此任务",
                    actor="ai",
                )
            )
        issues, deliverables, notes = _attach_segment_assets(db, item, task)
        item.status = "accepted"
        item.reviewed_at = time.time()
        db.commit()
        result = serialize_task(db, task)
        result["auto_attached"] = {
            "issues": issues,
            "deliverables": deliverables,
            "notes": notes,
        }
        return result

    if item.kind == "issue":
        task_id = payload.task_id
        if not task_id:
            raise HTTPException(status_code=400, detail="接受问题需要提供 task_id")
        task = db.get(Task, task_id)
        if not task or task.deleted_at is not None:
            raise HTTPException(status_code=404, detail="任务不存在")
        title = str(data.get("title") or "未命名问题")[:300]
        existing_titles = [
            value
            for value in db.scalars(select(Issue.title).where(Issue.task_id == task.id))
        ]
        if any(similarity(title, existing) >= 85 for existing in existing_titles):
            item.status = "accepted"
            item.reviewed_at = time.time()
            db.commit()
            return {"ok": True, "duplicate": True, "task_id": task.id}
        issue = Issue(
            task_id=task.id,
            title=title,
            detail=data.get("detail"),
            severity=data.get("severity") or "medium",
            source_message_id=(item.source_message_ids or [None])[0],
        )
        db.add(issue)
        db.add(TaskEvent(task_id=task.id, type="issue_added", note=issue.title))
        item.status = "accepted"
        item.reviewed_at = time.time()
        db.commit()
        return {"ok": True, "issue_id": issue.id, "task_id": task.id}

    if item.kind == "deliverable":
        task_id = payload.task_id
        if not task_id:
            raise HTTPException(status_code=400, detail="接受交付物需要提供 task_id")
        task = db.get(Task, task_id)
        if not task or task.deleted_at is not None:
            raise HTTPException(status_code=404, detail="任务不存在")
        path = str(data.get("path_or_url") or "")
        title = str(data.get("title") or os.path.basename(path))[:300]
        classification = classify_deliverable(path, title)
        if not classification["ok"]:
            item.status = "rejected"
            item.reviewed_at = time.time()
            item.payload = {**data, "reject_reason": classification["reason"]}
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=f"该文件不属于交付物：{classification['reason']}",
            )
        existing = db.scalar(
            select(Deliverable).where(
                Deliverable.task_id == task.id,
                Deliverable.path_or_url == path,
            )
        )
        if existing:
            item.status = "accepted"
            item.reviewed_at = time.time()
            db.commit()
            return {"ok": True, "deliverable_id": existing.id, "task_id": task.id}
        exists = bool(path and os.path.exists(path))
        group_key, logical_name = logical_group(
            title, path, data.get("logical_name")
        )
        version_at = data.get("version_at") or file_timestamp(path)
        intermediate = bool(
            data.get("is_intermediate", classification["is_intermediate"])
        )
        final = data.get("is_final")
        if final is None:
            final = is_final_by_name(title, path) and not intermediate
        deliverable = Deliverable(
            task_id=task.id,
            file_id=data.get("file_id"),
            title=title,
            type=data.get("type") or "file",
            path_or_url=path,
            file_size=os.path.getsize(path) if exists and os.path.isfile(path) else None,
            exists_flag=exists,
            attach_mode="auto_referenced",
            confidence=data.get("confidence"),
            source_message_id=(item.source_message_ids or [None])[0],
            group_key=group_key,
            logical_name=logical_name,
            version_label=data.get("version") or version_label(path, title, version_at),
            version_at=version_at,
            is_final=bool(final),
            is_intermediate=intermediate,
        )
        db.add(deliverable)
        db.add(TaskEvent(task_id=task.id, type="deliverable_added", note=title))
        item.status = "accepted"
        item.reviewed_at = time.time()
        db.flush()
        from ..services.deliverable_service import recompute_finals

        recompute_finals(db, task.id)
        db.commit()
        return {"ok": True, "deliverable_id": deliverable.id, "task_id": task.id}

    if item.kind == "note":
        task_id = payload.task_id
        if not task_id:
            raise HTTPException(status_code=400, detail="接受笔记需要提供 task_id")
        task = db.get(Task, task_id)
        if not task or task.deleted_at is not None:
            raise HTTPException(status_code=404, detail="任务不存在")
        summary = str(data.get("summary") or "").strip()
        if not summary:
            raise HTTPException(status_code=400, detail="笔记内容为空")
        note_text = f"[{data.get('category') or 'note'}] {summary}"
        existing = db.scalar(
            select(TaskEvent).where(
                TaskEvent.task_id == task.id,
                TaskEvent.type == "ai_note",
                TaskEvent.note == note_text,
            )
        )
        if existing is None:
            db.add(
                TaskEvent(
                    task_id=task.id,
                    type="ai_note",
                    note=note_text,
                    actor="ai",
                )
            )
        item.status = "accepted"
        item.reviewed_at = time.time()
        db.commit()
        return {"ok": True, "task_id": task.id}

    if item.kind == "project":
        name = str(data.get("name") or payload.title or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="项目名称为空")
        project = db.scalar(select(Project).where(Project.name == name))
        if not project:
            project = Project(name=name, description=data.get("description"))
            db.add(project)
            db.flush()
        item.status = "accepted"
        item.reviewed_at = time.time()
        db.commit()
        return {"ok": True, "project_id": project.id}

    item.status = "accepted"
    item.reviewed_at = time.time()
    db.commit()
    return {"ok": True, "note": "已标记为已读"}


@router.post("/{item_id}/reject")
def reject_item(item_id: int, payload: InboxReject | None = None, db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    item.status = "rejected"
    item.reviewed_at = time.time()
    if payload and payload.reason:
        item.payload = {**(item.payload or {}), "reject_reason": payload.reason}
    db.commit()
    return {"ok": True}


@router.post("/{item_id}/retry")
def retry_item(item_id: int, db: Session = Depends(get_db)):
    item = _get_item(db, item_id)
    if not item.segment_id:
        raise HTTPException(status_code=400, detail="该条目没有关联片段")
    db.query(InboxItem).filter(
        InboxItem.segment_id == item.segment_id,
        InboxItem.status == "pending",
    ).delete(synchronize_session=False)
    segment = db.get(Segment, item.segment_id)
    if segment:
        segment.extract_status = "pending"
        segment.extract_error = None
    db.commit()
    return {"ok": True, "segment_id": item.segment_id}


@router.post("/dedupe")
def dedupe(db: Session = Depends(get_db)):
    from ..ai.deduper import dedupe_pending

    result = dedupe_pending(db)
    db.commit()
    return result


@router.post("/bulk")
def bulk_action(
    action: str = Query(pattern="^(accept|reject)$"),
    ids: str = Query(description="逗号分隔的条目 id"),
    db: Session = Depends(get_db),
):
    results = []
    for raw in ids.split(","):
        try:
            item_id = int(raw.strip())
        except ValueError:
            continue
        try:
            if action == "accept":
                result = accept_item(item_id, InboxAccept(), force=True, db=db)
            else:
                result = reject_item(item_id, None, db=db)
            results.append({"id": item_id, "ok": True, "result": result})
        except HTTPException as exc:
            results.append({"id": item_id, "ok": False, "error": exc.detail})
    return {"results": results}
