"""Integration test: DynamoDB chat history per-user isolation + persistence (Step 8).

Skips unless DynamoDB-local is reachable at DYNAMODB_ENDPOINT.
"""

from __future__ import annotations

import socket
import uuid
from urllib.parse import urlparse

import pytest

from core.config import get_settings
from core.history import DynamoChatHistory


def _dynamo_reachable() -> bool:
    # Env-driven: whatever DYNAMODB_ENDPOINT points at (default 2003 per .env.example).
    parsed = urlparse(get_settings().dynamodb_endpoint)
    host, port = parsed.hostname or "localhost", parsed.port or 2003
    sock = socket.socket()
    sock.settimeout(1.0)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


@pytest.fixture(scope="module")
def history() -> DynamoChatHistory:
    if not _dynamo_reachable():
        pytest.skip(f"DynamoDB-local not reachable at {get_settings().dynamodb_endpoint}")
    store = DynamoChatHistory()
    store.ensure_table()
    return store


def test_messages_persist_and_round_trip(history: DynamoChatHistory) -> None:
    user, session = f"u-{uuid.uuid4().hex[:8]}", "s1"
    history.add_message(user, session, "human", "hello")
    history.add_message(user, session, "ai", "hi there")
    messages = history.get_messages(user, session)
    assert [m.content for m in messages] == ["hello", "hi there"]  # persisted + ordered


def test_per_user_isolation(history: DynamoChatHistory) -> None:
    user_a, user_b, session = f"a-{uuid.uuid4().hex[:8]}", f"b-{uuid.uuid4().hex[:8]}", "s1"
    history.add_message(user_a, session, "human", "secret from A")
    # user B (same session id) must NOT see user A's messages — the demo's shared-session bug
    assert history.get_messages(user_b, session) == []
    assert [m.content for m in history.get_messages(user_a, session)] == ["secret from A"]


def test_clear_session_leaves_other_sessions(history: DynamoChatHistory) -> None:
    user = f"u-{uuid.uuid4().hex[:8]}"
    history.add_message(user, "s1", "human", "in s1")
    history.add_message(user, "s2", "human", "in s2")
    assert history.clear_session(user, "s1") == 1
    assert history.get_messages(user, "s1") == []
    assert [m.content for m in history.get_messages(user, "s2")] == ["in s2"]


def test_delete_user_is_right_to_be_forgotten(history: DynamoChatHistory) -> None:
    user = f"u-{uuid.uuid4().hex[:8]}"
    history.add_message(user, "s1", "human", "a")
    history.add_message(user, "s2", "ai", "b")
    assert history.delete_user(user) == 2  # all sessions, one call
    assert history.get_messages(user, "s1") == []
    assert history.get_messages(user, "s2") == []


def test_export_user_dsar(history: DynamoChatHistory) -> None:
    user = f"u-{uuid.uuid4().hex[:8]}"
    history.add_message(user, "s1", "human", "hello")
    history.add_message(user, "s1", "ai", "hi there")
    export = {(e["session_id"], e["role"], e["content"]) for e in history.export_user(user)}
    assert ("s1", "human", "hello") in export
    assert ("s1", "ai", "hi there") in export
