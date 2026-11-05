from __future__ import annotations

import logging
import re
import secrets
import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config
from ..ai.client import AIError, chat_json
from ..ai.deduper import similarity
from ..db import get_setting
from ..models import (
    MessageCache,
    PendingConfirmation,
    ProcessedIntent,
    SessionCache,
    SyncState,
    Task,
)
from .notify_service import send_text
from .task_link_service import active_tasks_for_chat, chat_id_for_session

logger = logging.getLogger(__name__)

EXPLICIT_START = re.compile(
    r"^\s*(?:\d+[.)、]\s*)?(?:开始|新建|创建|新增)任务\s*[:：]\s*(.+)"
)
EXPLICIT_COMPLETE = re.compile(
    r"^\s*(?:\d+[.)、]\s*)?(?:完成|结束|关闭|收尾)任务\s*[:：]\s*(.+)"
)
EXPLICIT_FINAL = re.compile(
    r"^\s*(?:\d+[.)、]\s*)?(?:定稿|交付)\s*[:：]\s*(.+)"
)

START_HINTS = (
    "开始做", "开始搞", "开始弄", "开始这个", "启动", "着手", "我要做",
    "我准备做", "帮我做", "开始任务", "新任务", "做一个",
)
COMPLETE_HINTS = (
    "完成了", "做完了", "搞定了", "弄完了", "定稿了", "交付了", "收尾了",
    "结束这个", "已完成", "已经完成", "可以交付", "可以定稿",
)

SYSTEM_MARKERS = (
    "[CONTEXT COMPACTION",
    "[OUT-OF-BAND USER MESSAGE",
    "[SYSTEM",
    "Gateway message origin",
    "REFERENCE ONLY",
)

REPLY_ONLY = re.compile(
    r"^\s*(?:#?[A-F0-9]{4}\s*)?(?:加入|好|可以|是|确认|要|添加|建|不用|不要|不|否|"
    r"忽略|取消|完成|已完成|结束|还没|未完成|a|b|新任务)\s*$",
    re.IGNORECASE,
)

LLM_SYSTEM = """你是任务意图识别器。只输出 JSON，不要解释。
判断每条用户消息是否在「开始一个具体工作任务」或「完成一个具体工作任务」。
- start_task：用户明确要开始做一件具体的工作/项目。
- complete_task：用户明确说某件具体工作已经完成、定稿或交付。
- none：闲聊、提问、让助手查资料、改一个字、普通讨论。
- 忽略要求助手盘点/汇总/提炼/生成总结/输出物目录/扫描文件等「元指令」，这些不是工作任务。
返回：{"items":[{"message_id":1,"intent":"start_task|complete_task|none","title":"...","confidence":0.0}]}
title 用用户原话中描述工作对象的部分，去掉“开始/完成/帮我”等动词。"""


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


def _clean_title(text: str) -> str:
    cleaned = re.sub(r"^\s*(?:\d+[.)、]|[a-zA-Z][.)、])\s*", "", text)
    cleaned = re.sub(
        r"^\s*(?:我开始|我要|我准备|帮我|请|麻烦)?\s*(?:做|搞|弄|开始|启动|着手)?\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(r"(?:了|吧|呢|啊|呀|。|！|!|，|,)\s*$", "", cleaned).strip()
    return cleaned[:120]


def _explicit_title(capture: str) -> str:
    match = re.search(r"《([^》]+)》", capture)
    if match:
        return match.group(1).strip()[:120]
    cleaned = re.sub(r"^[a-zA-Z0-9]+[.)、]\s*", "", capture).strip()
    cleaned = re.split(r"[，。；;\n]", cleaned)[0].strip()
    return _clean_title(cleaned) or capture.strip()[:120]


def heuristic_intent(text: str) -> tuple[str, str | None, float]:
    match = EXPLICIT_START.search(text)
    if match:
        return "start_task", _explicit_title(match.group(1)), 1.0
    match = EXPLICIT_COMPLETE.search(text)
    if match:
        return "complete_task", _explicit_title(match.group(1)), 1.0
    match = EXPLICIT_FINAL.search(text)
    if match:
        return "complete_task", _explicit_title(match.group(1)), 1.0

    if any(hint in text for hint in START_HINTS):
        match = re.search(
            r"(?:开始做|开始搞|开始弄|启动|着手|我要做|我准备做|帮我做)\s*(.{2,80})",
            text,
        )
        title = match.group(1) if match else text
        return "start_task", _clean_title(title), 0.65
    if any(hint in text for hint in COMPLETE_HINTS):
        match = re.search(
            r"(.{2,80}?)(?:已经)?(?:完成|做完|搞定|弄完|定稿|交付|收尾|结束)",
            text,
        )
        title = match.group(1) if match else text
        return "complete_task", _clean_title(title), 0.65
    return "none", None, 0.0


def _needs_llm(text: str, heuristic: tuple[str, str | None, float]) -> bool:
    if heuristic[0] != "start_task" and heuristic[0] != "complete_task":
        return False
    return heuristic[2] < 0.9


def classify_messages(
    db: Session, messages: list[MessageCache]
) -> dict[int, tuple[str, str | None, float]]:
    results: dict[int, tuple[str, str | None, float]] = {}
    candidates: list[MessageCache] = []
    for message in messages:
        text = (message.content or "").strip()
        if not text or REPLY_ONLY.match(text):
            results[message.hermes_message_id] = ("none", None, 0.0)
            continue
        if any(marker in text for marker in SYSTEM_MARKERS):
            results[message.hermes_message_id] = ("none", None, 0.0)
            continue
        intent = heuristic_intent(text)
        results[message.hermes_message_id] = intent
        if _needs_llm(text, intent):
            candidates.append(message)

    if not candidates:
        return results
    api_key = config.get_secret("DEEPSEEK_API_KEY")
    if not api_key:
        return results

    lines = "\n".join(
        f"{message.hermes_message_id}: {(message.content or '')[:500]}"
        for message in candidates[:20]
    )
    try:
        data, _tokens = chat_json(
            [
                {"role": "system", "content": LLM_SYSTEM},
                {"role": "user", "content": lines},
            ],
            api_key=api_key,
            base_url=get_setting(db, "ai.base_url", config.DEFAULT_DEEPSEEK_BASE_URL)
            or "",
            model=get_setting(db, "ai.model", config.DEFAULT_DEEPSEEK_MODEL) or "",
            max_tokens=1_500,
        )
    except AIError as exc:
        logger.warning("intent classification failed: %s", exc)
        return results

    for item in data.get("items") or []:
        try:
            message_id = int(item.get("message_id"))
            intent = str(item.get("intent") or "none")
            confidence = float(item.get("confidence") or 0)
            title = item.get("title")
        except (TypeError, ValueError):
            continue
        if intent not in {"start_task", "complete_task"} or confidence < 0.6:
            results[message_id] = ("none", None, 0.0)
            continue
        results[message_id] = (intent, (title or "").strip()[:120] or None, confidence)
    return results


def _new_code(db: Session) -> str:
    while True:
        code = "A" + secrets.token_hex(2).upper()
        if db.scalar(select(PendingConfirmation.id).where(PendingConfirmation.code == code)) is None:
            return code


def create_confirmation(
    db: Session, kind: str, payload: dict[str, Any], question: str
) -> PendingConfirmation:
    confirmation = PendingConfirmation(
        code=_new_code(db),
        kind=kind,
        payload=payload,
        status="pending",
        created_at=time.time(),
        expires_at=time.time() + 86_400,
    )
    db.add(confirmation)
    db.flush()
    text = f"{question}\n编号：#{confirmation.code}"
    send_result = send_text(
        db,
        text,
        kind="task_confirm",
        title="任务确认",
    ) or {}
    confirmation.payload = {
        **payload,
        "question_sent": bool(send_result.get("ok")),
        "question_error": send_result.get("error"),
    }
    db.flush()
    return confirmation


def _start_question(title: str) -> str:
    return (
        "🆕 检测到新任务\n"
        f"《{title}》\n"
        "要加入工作台吗？\n"
        "回复「加入」或「不用」"
    )


def _complete_question(title: str) -> str:
    return (
        "✅ 确认完成任务\n"
        f"《{title}》\n"
        "回复「完成」或「取消」"
    )


def scan_intents(
    db: Session, *, limit: int = 30, since: float | None = None
) -> dict[str, Any]:
    cursor = _ensure_cursor(db, "intent_cursor.message_id")
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
        return {"checked": 0, "starts": 0, "completes": 0, "questions": []}

    ids = [message.hermes_message_id for message in messages]
    processed_ids = set(
        db.scalars(
            select(ProcessedIntent.message_id).where(
                ProcessedIntent.message_id.in_(ids)
            )
        )
    )
    messages = [
        message for message in messages if message.hermes_message_id not in processed_ids
    ]
    if not messages:
        return {"checked": 0, "starts": 0, "completes": 0, "questions": []}

    processed_hashes = {
        row[0]
        for row in db.execute(
            select(MessageCache.content_hash)
            .join(
                ProcessedIntent,
                ProcessedIntent.message_id == MessageCache.hermes_message_id,
            )
            .where(
                ProcessedIntent.intent.in_(["start_task", "complete_task"]),
                MessageCache.content_hash.is_not(None),
            )
        )
        if row[0]
    }
    pending_starts = list(
        db.scalars(
            select(PendingConfirmation).where(
                PendingConfirmation.kind == "start_task",
                PendingConfirmation.status == "pending",
            )
        )
    )
    pending_completes = list(
        db.scalars(
            select(PendingConfirmation).where(
                PendingConfirmation.kind == "complete_task",
                PendingConfirmation.status == "pending",
            )
        )
    )

    classified = classify_messages(db, messages)
    starts = completes = 0
    questions: list[dict[str, Any]] = []
    max_seen = cursor

    def mark(message_id: int, value: str) -> None:
        db.add(ProcessedIntent(message_id=message_id, intent=value))

    for message in messages:
        max_seen = max(max_seen, message.hermes_message_id)
        intent, title, confidence = classified.get(
            message.hermes_message_id, ("none", None, 0.0)
        )
        chat_id = chat_id_for_session(db, message.session_id)
        active = active_tasks_for_chat(db, chat_id)
        text = (message.content or "").strip()

        if intent == "start_task":
            if not title:
                title = _clean_title(text)
            if message.content_hash and message.content_hash in processed_hashes:
                mark(message.hermes_message_id, "duplicate_content")
                continue
            if any(similarity(title, task.title) >= 75 for task in active):
                mark(message.hermes_message_id, "start_skipped")
                continue
            if any(
                (item.payload or {}).get("chat_id") == chat_id
                and similarity(title, (item.payload or {}).get("title") or "") >= 75
                for item in pending_starts
            ):
                mark(message.hermes_message_id, "start_duplicate_pending")
                continue
            confirmation = create_confirmation(
                db,
                "start_task",
                {
                    "title": title,
                    "chat_id": chat_id,
                    "session_id": message.session_id,
                    "message_ids": [message.hermes_message_id],
                    "started_at": message.timestamp or time.time(),
                    "source_excerpt": text[:500],
                    "confidence": confidence,
                },
                _start_question(title),
            )
            mark(message.hermes_message_id, "start_task")
            if message.content_hash:
                processed_hashes.add(message.content_hash)
            pending_starts.append(confirmation)
            questions.append(
                {
                    "code": confirmation.code,
                    "kind": "start_task",
                    "title": title,
                    "sent": bool((confirmation.payload or {}).get("question_sent")),
                    "error": (confirmation.payload or {}).get("question_error"),
                }
            )
            starts += 1
            continue

        if intent == "complete_task":
            if message.content_hash and message.content_hash in processed_hashes:
                mark(message.hermes_message_id, "duplicate_content")
                continue
            scored = sorted(
                ((similarity(title or text, task.title), task) for task in active),
                key=lambda pair: pair[0],
                reverse=True,
            )
            if not scored:
                mark(message.hermes_message_id, "complete_skipped")
                continue
            best_score, best_task = scored[0]
            if best_score < 50 and len(active) > 1:
                mark(message.hermes_message_id, "complete_skipped")
                continue
            if any(
                int((item.payload or {}).get("task_id") or 0) == best_task.id
                for item in pending_completes
            ):
                mark(message.hermes_message_id, "complete_duplicate_pending")
                continue
            confirmation = create_confirmation(
                db,
                "complete_task",
                {
                    "task_id": best_task.id,
                    "title": best_task.title,
                    "chat_id": chat_id,
                    "message_ids": [message.hermes_message_id],
                    "completed_at": message.timestamp or time.time(),
                    "source_excerpt": text[:500],
                    "candidate_task_ids": [task.id for _score, task in scored[:3]],
                    "confidence": confidence,
                },
                _complete_question(best_task.title),
            )
            mark(message.hermes_message_id, "complete_task")
            if message.content_hash:
                processed_hashes.add(message.content_hash)
            pending_completes.append(confirmation)
            questions.append(
                {
                    "code": confirmation.code,
                    "kind": "complete_task",
                    "title": best_task.title,
                    "sent": bool((confirmation.payload or {}).get("question_sent")),
                    "error": (confirmation.payload or {}).get("question_error"),
                }
            )
            completes += 1
            continue

        mark(message.hermes_message_id, "none")

    if max_seen > cursor:
        _set_cursor(db, "intent_cursor.message_id", max_seen)
    db.flush()
    return {
        "checked": len(messages),
        "starts": starts,
        "completes": completes,
        "questions": questions,
    }
