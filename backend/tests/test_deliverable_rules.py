from app.services.deliverable_rules import (
    classify_deliverable,
    is_final_by_name,
    logical_group,
    version_label,
)
from app.services.deliverable_service import dedupe_deliverables
from app.models import Deliverable


def test_scratch_script_is_not_a_deliverable():
    result = classify_deliverable(
        r"D:\.hermes\cache\scratch\build_v45.py", "全景图生成器脚本"
    )
    assert result["ok"] is False


def test_scratch_html_is_not_a_deliverable():
    result = classify_deliverable(
        r"D:\.hermes\cache\scratch\ks_v30_video.html", "视频 HTML（scratch 中间产物）"
    )
    assert result["ok"] is False


def test_final_mp4_is_a_deliverable():
    result = classify_deliverable(
        r"D:\hermes\outputs\documents\demo_overview_v3.0_讲解视频_1080p_4min_20261103.mp4",
        "产品演示 v3.0 讲解视频 MP4 成片",
    )
    assert result["ok"] is True
    assert result["is_intermediate"] is False
    assert is_final_by_name("MP4 成片", "a.mp4") is True


def test_sample_is_intermediate():
    result = classify_deliverable(
        r"D:\hermes\outputs\documents\demo_overview_v3.0_视频样片_0-24s_20261103.mp4",
        "24 秒视频样片",
    )
    assert result["ok"] is True
    assert result["is_intermediate"] is True


def test_same_logical_group_for_mp4_and_html():
    mp4 = r"D:\hermes\outputs\documents\demo_overview_v3.0_讲解视频_1080p_4min_20261103.mp4"
    html = r"D:\hermes\outputs\documents\demo_overview_v3.0_讲解视频_HTML_20261103.html"
    assert logical_group("MP4 成片", mp4)[0] == logical_group("HTML 交互版", html)[0]


def test_version_label_contains_date_and_format():
    label = version_label(
        r"D:\hermes\outputs\documents\demo_overview_v3.0_讲解视频_1080p_4min_20261103.mp4"
    )
    assert "2026-11-03" in label
    assert "MP4" in label


def test_dedupe_deliverables_collapses_same_path(db):
    first = Deliverable(
        task_id=1,
        title="最终版",
        path_or_url=r"F:\outputs\a.mp4",
        is_intermediate=False,
        is_final=True,
        version_at=2,
    )
    second = Deliverable(
        task_id=1,
        title="过程版",
        path_or_url=r"F:\outputs\a.mp4",
        is_intermediate=True,
        is_final=False,
        version_at=1,
    )
    db.add_all([first, second])
    db.commit()
    assert dedupe_deliverables(db) == 1
    remaining = db.query(Deliverable).all()
    assert len(remaining) == 1
    assert remaining[0].title == "最终版"
