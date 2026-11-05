from app.ingest.normalizer import (
    clean_text,
    extract_media_paths,
    extract_windows_paths,
    normalize_message,
)


def test_clean_text_strips_ansi_and_normalizes_newlines():
    raw = "\x1b[31m红色\x1b[0m\r\n第二行\x00"
    assert clean_text(raw) == "红色\n第二行"


def test_extract_media_paths():
    text = "完成\nMEDIA:D:\\hermes\\outputs\\a.mp4\n结束"
    assert extract_media_paths(text) == [r"D:\hermes\outputs\a.mp4"]


def test_extract_windows_paths_deduplicates():
    text = "见 `F:\\a\\b.pdf`，另见 F:\\a\\b.pdf。"
    paths = extract_windows_paths(text)
    assert paths == [r"F:\a\b.pdf"]


def test_normalize_message_truncates_tool_output():
    row = {
        "id": 1,
        "session_id": "s",
        "role": "tool",
        "content": "x" * 5000,
        "tool_name": "terminal",
        "timestamp": 1700000000,
    }
    result = normalize_message(row)
    assert result is not None
    assert result["truncated"] is True
    assert len(result["content"]) < 2100


def test_normalize_message_skips_session_meta():
    assert normalize_message({"id": 1, "role": "session_meta"}) is None
