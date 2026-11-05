from app.ingest.segmenter import segment_messages
from app.models import MessageCache


def _message(index: int, timestamp: float, role: str = "user") -> MessageCache:
    return MessageCache(
        hermes_message_id=index,
        session_id="s1",
        role=role,
        content=f"内容 {index}",
        content_hash=f"h{index}",
        timestamp=timestamp,
    )


def test_splits_on_two_hour_gap():
    base = 1_760_000_000  # local noon-ish; gaps stay within a day
    messages = [_message(i, base + i * 60) for i in range(4)]
    messages += [_message(i + 10, base + 4 * 60 + 3 * 3600 + i * 60) for i in range(4)]
    segments = segment_messages(messages)
    assert len(segments) == 2
    assert segments[0]["message_count"] == 4
    assert segments[1]["message_count"] == 4


def test_merges_small_fragment():
    base = 1_760_000_000
    messages = [_message(i, base + i * 60) for i in range(6)]
    segments = segment_messages(messages)
    assert len(segments) == 1
    assert segments[0]["message_count"] == 6


def test_skips_pure_tool_segments():
    base = 1_760_000_000
    messages = [_message(i, base + i * 60, role="tool") for i in range(5)]
    assert segment_messages(messages) == []


def test_respects_max_messages():
    base = 1_760_000_000
    messages = [_message(i, base + i) for i in range(90)]
    segments = segment_messages(messages)
    assert all(segment["message_count"] <= 80 for segment in segments)
