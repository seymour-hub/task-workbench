from app.ai.deduper import (
    dedupe_pending,
    fingerprint,
    normalize_title,
    similarity,
)
from app.models import InboxItem


def test_normalize_title_removes_punctuation_and_spaces():
    assert normalize_title("制作 产品演示 视频（MP4 + HTML）") == normalize_title(
        "制作产品演示视频MP4HTML"
    )


def test_similar_titles_score_high():
    score = similarity(
        "制作 产品演示 v3.0 讲解视频（MP4 与 HTML 双版本）",
        "制作 产品演示 v3.0 讲解视频（HTML/MP4）",
    )
    assert score >= 82


def test_different_titles_score_low():
    assert similarity("修复字幕错位", "整理季度预算") < 50


def test_fingerprint_is_stable():
    assert fingerprint("  A  b  ") == fingerprint("a b")


def test_dedupe_pending_marks_near_duplicate(db):
    first = InboxItem(
        kind="task",
        payload={"title": "制作安全架构讲解视频（MP4 与 HTML）"},
        confidence=0.95,
        status="pending",
    )
    second = InboxItem(
        kind="task",
        payload={"title": "制作安全架构讲解视频（HTML/MP4）"},
        confidence=0.8,
        status="pending",
    )
    db.add_all([first, second])
    db.commit()
    result = dedupe_pending(db)
    assert result["marked"] == 1
    assert second.status == "duplicate"
    assert first.status == "pending"
