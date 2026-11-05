from __future__ import annotations

import logging
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from ..ai.extractor import extract_pending, pending_segment_count
from ..db import get_bool_setting, get_int_setting, get_setting, session_scope
from ..ingest.sync_service import sync_now
from ..models import DeliverableRoot
from .file_service import scan_root
from .notify_service import (
    send_digest,
    send_due_reminder,
    send_overdue_reminder,
    send_weekly,
)

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None
_last_tick_minute: str | None = None


def _sync_job() -> None:
    with session_scope() as db:
        if not get_bool_setting(db, "sync.enabled", True):
            return
        result = sync_now(db)
        if not result.get("ok"):
            logger.warning("sync failed: %s", result.get("error"))
            return
        try:
            from .workflow_service import process_after_sync

            workflow = process_after_sync(db)
            if any(
                workflow[key].get("resolved")
                or workflow[key].get("starts")
                or workflow[key].get("completes")
                or workflow[key].get("linked")
                for key in workflow
            ):
                logger.info("workflow: %s", workflow)
        except Exception:  # noqa: BLE001
            logger.exception("workflow after sync failed")


def _extract_job() -> None:
    with session_scope() as db:
        if not get_bool_setting(db, "extract.enabled", True):
            return
        if pending_segment_count(db) == 0:
            return
        result = extract_pending(db, limit=3)
        if result.get("processed") or result.get("failed"):
            logger.info("extract: %s", result)


def _file_scan_job() -> None:
    now = time.time()
    with session_scope() as db:
        roots = list(
            db.scalars(select(DeliverableRoot).where(DeliverableRoot.enabled.is_(True)))
        )
        default_interval = get_int_setting(db, "files.scan_interval_min", 30)
        max_files = get_int_setting(db, "files.max_files_per_root", 20_000)
        for root in roots:
            interval = (root.scan_interval_min or default_interval) * 60
            if root.last_scan_at and now - root.last_scan_at < interval:
                continue
            try:
                result = scan_root(db, root, max_files=max_files)
                logger.info("file scan %s: %s", root.label, result)
            except Exception:  # noqa: BLE001
                logger.exception("file scan failed for %s", root.path)


def _minute_tick() -> None:
    global _last_tick_minute
    now = datetime.now()
    minute_key = now.strftime("%Y-%m-%d %H:%M")
    if minute_key == _last_tick_minute:
        return
    _last_tick_minute = minute_key
    hhmm = now.strftime("%H:%M")

    with session_scope() as db:
        if not get_bool_setting(db, "notify.enabled", True):
            return
        if hhmm == (get_setting(db, "notify.due_time") or "09:05"):
            try:
                send_due_reminder(db)
            except Exception:  # noqa: BLE001
                logger.exception("due reminder failed")
        if hhmm == (get_setting(db, "notify.overdue_time") or "18:00"):
            try:
                send_overdue_reminder(db)
            except Exception:  # noqa: BLE001
                logger.exception("overdue reminder failed")
        if hhmm == (get_setting(db, "notify.digest_time") or "09:00"):
            try:
                send_digest(db)
            except Exception:  # noqa: BLE001
                logger.exception("digest failed")
        weekly_day = get_int_setting(db, "notify.weekly_day", 4)
        if now.weekday() == weekly_day and hhmm == (
            get_setting(db, "notify.weekly_time") or "18:00"
        ):
            try:
                send_weekly(db)
            except Exception:  # noqa: BLE001
                logger.exception("weekly report failed")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        _sync_job,
        IntervalTrigger(seconds=60),
        id="sync",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _extract_job,
        IntervalTrigger(minutes=10),
        id="extract",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _file_scan_job,
        IntervalTrigger(minutes=5),
        id="file_scan",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _minute_tick,
        IntervalTrigger(seconds=30),
        id="notify_tick",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("scheduler started with jobs: %s", [job.id for job in scheduler.get_jobs()])
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
