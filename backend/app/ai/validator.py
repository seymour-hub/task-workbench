from __future__ import annotations

import time
from typing import Any

from dateutil import parser as date_parser
from pydantic import ValidationError

from ..schemas import (
    AIDecision,
    AIDeliverable,
    AIIssue,
    AIMilestone,
    AITask,
    ExtractionResult,
)


def parse_due_at(value: str | None) -> float | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower() in {"null", "none", "无", "未提及"}:
        return None
    try:
        parsed = date_parser.parse(text)
    except (ValueError, OverflowError):
        return None
    if parsed.hour == 0 and parsed.minute == 0 and ":" not in text:
        parsed = parsed.replace(hour=18, minute=0)
    return parsed.timestamp()


def _clean_ids(values: list[int], allowed: set[int]) -> list[int]:
    result: list[int] = []
    for value in values or []:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number in allowed and number not in result:
            result.append(number)
    return result


def validate_extraction(raw: dict[str, Any], allowed_ids: set[int]) -> ExtractionResult:
    result = ExtractionResult()

    for item in raw.get("tasks") or []:
        if not isinstance(item, dict):
            continue
        try:
            task = AITask.model_validate(item)
        except ValidationError:
            continue
        task.evidence_message_ids = _clean_ids(task.evidence_message_ids, allowed_ids)
        if not task.title.strip() or not task.evidence_message_ids:
            continue
        task.title = task.title.strip()[:300]
        result.tasks.append(task)

    for item in raw.get("issues") or []:
        if not isinstance(item, dict):
            continue
        try:
            issue = AIIssue.model_validate(item)
        except ValidationError:
            continue
        issue.evidence_message_ids = _clean_ids(issue.evidence_message_ids, allowed_ids)
        if not issue.title.strip() or not issue.evidence_message_ids:
            continue
        result.issues.append(issue)

    for item in raw.get("deliverables") or []:
        if not isinstance(item, dict):
            continue
        try:
            deliverable = AIDeliverable.model_validate(item)
        except ValidationError:
            continue
        deliverable.evidence_message_ids = _clean_ids(
            deliverable.evidence_message_ids, allowed_ids
        )
        if not deliverable.title.strip() or not deliverable.path_or_url.strip():
            continue
        result.deliverables.append(deliverable)

    for item in raw.get("decisions") or []:
        if not isinstance(item, dict):
            continue
        try:
            decision = AIDecision.model_validate(item)
        except ValidationError:
            continue
        decision.evidence_message_ids = _clean_ids(
            decision.evidence_message_ids, allowed_ids
        )
        if decision.summary.strip():
            result.decisions.append(decision)

    for item in raw.get("next_steps") or []:
        if not isinstance(item, dict):
            continue
        try:
            step = AIDecision.model_validate(item)
        except ValidationError:
            continue
        step.evidence_message_ids = _clean_ids(step.evidence_message_ids, allowed_ids)
        if step.summary.strip():
            result.next_steps.append(step)

    for item in raw.get("milestones") or []:
        if not isinstance(item, dict):
            continue
        try:
            milestone = AIMilestone.model_validate(item)
        except ValidationError:
            continue
        milestone.evidence_message_ids = _clean_ids(
            milestone.evidence_message_ids, allowed_ids
        )
        if milestone.summary.strip() and milestone.evidence_message_ids:
            result.milestones.append(milestone)

    return result


def iso_from_epoch(value: float | None) -> str | None:
    if value is None:
        return None
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(value))
