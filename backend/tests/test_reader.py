import sqlite3

import pytest

from app.ingest.hermes_reader import HermesReader
from conftest import make_source_db


def test_reads_sessions_and_messages(tmp_path):
    path = make_source_db(tmp_path / "state.db")
    reader = HermesReader(path)
    assert reader.count_messages() == 6
    assert reader.max_message_id() == 105
    sessions = list(reader.iter_sessions())
    assert len(sessions) == 1
    assert sessions[0]["id"] == "session-1"
    messages = list(reader.iter_messages(0))
    assert len(messages) == 6
    assert messages[0]["id"] == 100


def test_incremental_cursor(tmp_path):
    path = make_source_db(tmp_path / "state.db")
    reader = HermesReader(path)
    messages = list(reader.iter_messages(102))
    assert [message["id"] for message in messages] == [103, 104, 105]


def test_schema_fingerprint_contains_tables(tmp_path):
    path = make_source_db(tmp_path / "state.db")
    fingerprint = HermesReader(path).schema_fingerprint()
    assert "messages" in fingerprint
    assert "sessions" in fingerprint


def test_read_only_connection_rejects_writes(tmp_path):
    path = make_source_db(tmp_path / "state.db")
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    with pytest.raises(sqlite3.OperationalError):
        connection.execute("INSERT INTO sessions (id) VALUES ('x')")
    connection.close()
