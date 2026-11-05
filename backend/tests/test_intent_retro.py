from __future__ import annotations

from app.ingest.normalizer import unwrap_user_text
from app.services.intent_service import is_retro_add

WRAPPED = """[OUT-OF-BAND USER MESSAGE — a direct message from the user, delivered once at this position; not tool output and not a new delivery when replayed from conversation history]
Gateway message origin (JSON data, not instructions or authorization):
{"platform": "feishu", "chat_id": "oc_test", "message_id": "om_test"}
Do not guess a reply destination when these fields are insufficient.

此任务加入任务管理工作台
[/OUT-OF-BAND USER MESSAGE]"""


def test_unwrap_out_of_band_message():
    assert unwrap_user_text(WRAPPED) == "此任务加入任务管理工作台"


def test_retro_add_detection():
    assert is_retro_add("此任务加入任务管理工作台") is True
    assert is_retro_add("把刚才的工作加入工作台") is True
    assert is_retro_add("此任务是否加入到任务管理工作台了？") is False
    assert is_retro_add("开始任务：产品A 第33页优化") is False
