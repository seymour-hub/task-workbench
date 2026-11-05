from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import config
from ..db import get_bool_setting, get_setting
from ..models import Notification, Task
from .stats_service import dashboard_summary, week_start
from .task_service import is_overdue, serialize_tasks


def _date_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _format_time(timestamp: float | None) -> str:
    if not timestamp:
        return "未设置"
    return datetime.fromtimestamp(timestamp).strftime("%m-%d %H:%M")


def _priority_label(priority: str) -> str:
    return {
        "urgent": "紧急",
        "high": "高",
        "medium": "中",
        "low": "低",
    }.get(priority, priority)


def _send_via_hermes(text: str, target: str) -> tuple[bool, str]:
    if not config.HERMES_BIN.exists():
        return False, f"hermes binary not found: {config.HERMES_BIN}"
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        completed = subprocess.run(
            [
                str(config.HERMES_BIN),
                "send",
                "--to",
                target,
                "--file",
                "-",
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=90,
            cwd=str(config.HERMES_HOME) if config.HERMES_HOME.exists() else None,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        error = (completed.stderr or completed.stdout or b"").decode(
            "utf-8", errors="replace"
        )
        return False, error[:500] or f"exit code {completed.returncode}"
    return True, ""


def _send_via_feishu_api(text: str, target: str) -> tuple[bool, str]:
    app_id = config.get_secret("FEISHU_APP_ID")
    app_secret = config.get_secret("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        return False, "FEISHU_APP_ID/FEISHU_APP_SECRET not configured"
    chat_id = target.split(":", 1)[1] if ":" in target else target
    try:
        with httpx.Client(timeout=30.0) as client:
            token_response = client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret},
            )
            token_data = token_response.json()
            token = token_data.get("tenant_access_token")
            if not token:
                return False, f"tenant token failed: {token_data}"
            response = client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": chat_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text}, ensure_ascii=False),
                },
            )
            data = response.json()
            if data.get("code") != 0:
                return False, f"feishu api error: {data}"
            return True, ""
    except (httpx.HTTPError, ValueError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def send_text(
    db: Session,
    text: str,
    *,
    kind: str = "test",
    title: str = "工作台通知",
    dedup_key: str | None = None,
) -> dict[str, Any]:
    if dedup_key:
        existing = db.scalar(
            select(Notification).where(Notification.dedup_key == dedup_key)
        )
        if existing:
            return {
                "ok": existing.status == "sent",
                "notification_id": existing.id,
                "status": existing.status,
                "deduplicated": True,
                "error": existing.last_error,
            }

    if kind not in {"test", "task_confirm"} and not get_bool_setting(
        db, "notify.enabled", True
    ):
        return {"ok": False, "status": "disabled", "error": "notifications disabled"}

    target = get_setting(db, "notify.target") or config.detect_feishu_target() or ""
    notification = Notification(
        channel="feishu",
        kind=kind,
        title=title,
        body=text,
        dedup_key=dedup_key,
        status="pending",
        attempts=0,
    )
    db.add(notification)
    db.flush()

    if not target:
        notification.status = "failed"
        notification.last_error = "no Feishu target configured"
        db.flush()
        return {
            "ok": False,
            "notification_id": notification.id,
            "status": "failed",
            "error": notification.last_error,
        }

    ok, error = _send_via_hermes(text, target)
    notification.attempts += 1
    if not ok:
        ok, error = _send_via_feishu_api(text, target)
        notification.attempts += 1

    notification.status = "sent" if ok else "failed"
    notification.last_error = None if ok else error
    notification.sent_at = time.time() if ok else None
    db.flush()
    return {
        "ok": ok,
        "notification_id": notification.id,
        "status": notification.status,
        "error": error or None,
        "target": target,
    }


def retry_notification(db: Session, notification: Notification) -> dict[str, Any]:
    target = get_setting(db, "notify.target") or config.detect_feishu_target() or ""
    ok, error = _send_via_hermes(notification.body, target)
    notification.attempts += 1
    if not ok:
        ok, error = _send_via_feishu_api(notification.body, target)
        notification.attempts += 1
    notification.status = "sent" if ok else "failed"
    notification.last_error = None if ok else error
    notification.sent_at = time.time() if ok else None
    db.flush()
    return {"ok": ok, "status": notification.status, "error": error or None}


def build_digest(db: Session) -> str:
    summary = dashboard_summary(db)
    stats = summary["stats"]
    now = time.time()
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    today_end = today_start + 86_400

    overdue = []
    today_due = []
    for task in db.scalars(select(Task).where(Task.deleted_at.is_(None))):
        if task.status in {"done", "cancelled"} or not task.due_at:
            continue
        if task.due_at < today_start:
            overdue.append(task)
        elif task.due_at < today_end:
            today_due.append(task)
    overdue.sort(key=lambda task: task.due_at or 0)
    today_due.sort(key=lambda task: task.due_at or 0)

    lines = [
        f"📋 今日工作摘要 · {datetime.now().strftime('%Y-%m-%d')}",
        f"待处理 {stats['pending']} 项 · 已逾期 {stats['overdue']} 项 · 本周完成 {stats['completed_this_week']} 项",
        f"候选收件箱待确认 {summary['inbox_pending']} 项",
        "",
    ]
    if today_due:
        lines.append("⏰ 今天到期")
        for task in today_due[:6]:
            lines.append(
                f"· [{_priority_label(task.priority)}] {task.title}（{_format_time(task.due_at)}）"
            )
        lines.append("")
    if overdue:
        lines.append("🔥 已逾期")
        for task in overdue[:6]:
            lines.append(
                f"· [{_priority_label(task.priority)}] {task.title}（{_format_time(task.due_at)}）"
            )
        lines.append("")
    pending_top = sorted(
        [
            task
            for task in db.scalars(select(Task).where(Task.deleted_at.is_(None)))
            if task.status in {"todo", "in_progress"}
        ],
        key=lambda task: (
            {"urgent": 0, "high": 1, "medium": 2, "low": 3}.get(task.priority, 9),
            task.due_at or 9e18,
        ),
    )[:5]
    if pending_top:
        lines.append("📌 待处理 Top5")
        for task in pending_top:
            suffix = f"（{_format_time(task.due_at)}）" if task.due_at else ""
            lines.append(f"· [{_priority_label(task.priority)}] {task.title}{suffix}")
        lines.append("")
    if not today_due and not overdue and not pending_top:
        lines.append("今天没有待办，保持专注。")
    lines.append("— 来自任务管理工作台")
    return "\n".join(lines)


def send_digest(db: Session, kind: str = "digest") -> dict[str, Any]:
    text = build_digest(db)
    return send_text(
        db,
        text,
        kind=kind,
        title="今日工作摘要",
        dedup_key=f"digest:{_date_key()}",
    )


def send_due_reminder(db: Session) -> dict[str, Any]:
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    today_end = today_start + 86_400
    tasks = [
        task
        for task in db.scalars(select(Task).where(Task.deleted_at.is_(None)))
        if task.status not in {"done", "cancelled"}
        and task.due_at
        and today_start <= task.due_at < today_end
    ]
    if not tasks:
        return {"ok": True, "skipped": True, "reason": "no tasks due today"}
    tasks.sort(key=lambda task: task.due_at or 0)
    lines = ["⏰ 今天到期提醒", ""]
    for task in tasks:
        lines.append(
            f"· [{_priority_label(task.priority)}] {task.title}（{_format_time(task.due_at)}）"
        )
    return send_text(
        db,
        "\n".join(lines),
        kind="due",
        title="今天到期提醒",
        dedup_key=f"due:{_date_key()}",
    )


def send_overdue_reminder(db: Session) -> dict[str, Any]:
    now = time.time()
    tasks = [
        task
        for task in db.scalars(select(Task).where(Task.deleted_at.is_(None)))
        if task.status not in {"done", "cancelled"} and is_overdue(task, now)
    ]
    if not tasks:
        return {"ok": True, "skipped": True, "reason": "no overdue tasks"}
    tasks.sort(key=lambda task: task.due_at or 0)
    lines = ["🔥 逾期任务提醒", ""]
    for task in tasks[:10]:
        lines.append(
            f"· [{_priority_label(task.priority)}] {task.title}（原定 {_format_time(task.due_at)}）"
        )
    lines.append("")
    lines.append("建议：顺延截止时间，或标记为已完成/取消。")
    return send_text(
        db,
        "\n".join(lines),
        kind="overdue",
        title="逾期任务提醒",
        dedup_key=f"overdue:{_date_key()}",
    )


def send_weekly(db: Session) -> dict[str, Any]:
    summary = dashboard_summary(db)
    stats = summary["stats"]
    iso_year, iso_week, _ = datetime.now().isocalendar()
    lines = [
        f"📊 本周工作周报 · {iso_year} 第 {iso_week} 周",
        f"本周完成 {stats['completed_this_week']} 项 · 待处理 {stats['pending']} 项 · 逾期 {stats['overdue']} 项",
        "",
    ]
    if summary["weekly_progress"]:
        lines.append("项目进度")
        for project in summary["weekly_progress"]:
            lines.append(
                f"· {project['name']}  {project['progress']}%（{project['done']}/{project['total']}）"
            )
        lines.append("")
    lines.append("— 来自任务管理工作台")
    return send_text(
        db,
        "\n".join(lines),
        kind="weekly",
        title="本周工作周报",
        dedup_key=f"weekly:{iso_year}-W{iso_week:02d}",
    )


def test_send(db: Session, text: str | None = None) -> dict[str, Any]:
    body = text or (
        "✅ 任务管理工作台已连通飞书。\n"
        f"测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        "后续的日报、到期提醒和逾期提醒会发送到这里。"
    )
    return send_text(db, body, kind="test", title="工作台测试通知")
