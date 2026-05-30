"""Integration test: DynamoDB chat history per-user isolation + persistence (Step 8).

Skips unless DynamoDB-local is reachable on localhost:8000.
"""

from __future__ import annotations

import socket
import uuid

import pytest

from core.history import DynamoChatHistory


def _dynamo_reachable() -> bool:
    sock = socket.socket()
    sock.settimeout(1.0)
    try:
        sock.connect(("localhost", 8000))
        return True
    except OSError:
        return False
    finally:
        sock.close()


@pytest.fixture(scope="module")
def history() -> DynamoChatHistory:
    if not _dynamo_reachable():
        pytest.skip("DynamoDB-local not reachable on localhost:8000")
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
