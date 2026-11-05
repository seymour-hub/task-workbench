import time

from app.ai.validator import parse_due_at, validate_extraction


def test_drops_tasks_without_valid_evidence_and_clamps_confidence():
    raw = {
        "tasks": [
            {
                "title": "整理纪要",
                "confidence": 1.8,
                "evidence_message_ids": [1, 999],
            },
            {
                "title": "没有证据的任务",
                "confidence": 0.9,
                "evidence_message_ids": [999],
            },
        ],
        "issues": [],
        "deliverables": [],
        "decisions": [],
        "next_steps": [],
    }
    result = validate_extraction(raw, {1, 2})
    assert len(result.tasks) == 1
    assert result.tasks[0].confidence == 1.0
    assert result.tasks[0].evidence_message_ids == [1]


def test_rejects_deliverable_without_path():
    raw = {
        "tasks": [],
        "issues": [],
        "deliverables": [{"title": "报告", "path_or_url": ""}],
        "decisions": [],
        "next_steps": [],
    }
    result = validate_extraction(raw, {1})
    assert result.deliverables == []


def test_parse_due_at_date_only_defaults_to_evening():
    timestamp = parse_due_at("2026-11-05")
    assert timestamp is not None
    local = time.localtime(timestamp)
    assert (local.tm_hour, local.tm_min) == (18, 0)


def test_parse_due_at_invalid_returns_none():
    assert parse_due_at("下周找个时间") is None
    assert parse_due_at(None) is None
