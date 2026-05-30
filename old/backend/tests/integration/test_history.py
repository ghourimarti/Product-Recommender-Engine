"""Step 8: chat history is per-session-isolated and persists.

Exercises the *production* component (SQLChatMessageHistory) the chain now uses, on a
sqlite file (keyless). This is the regression test for the Phase-0 shared-session bug.
"""
from __future__ import annotations


def test_sessions_are_isolated(tmp_path):
    from langchain_community.chat_message_histories import SQLChatMessageHistory

    conn = f"sqlite:///{tmp_path / 'hist.db'}"
    a = SQLChatMessageHistory(session_id="user-a", connection=conn)
    b = SQLChatMessageHistory(session_id="user-b", connection=conn)

    a.add_user_message("show me headphones")
    b.add_user_message("show me shoes")

    assert [m.content for m in a.messages] == ["show me headphones"]
    assert [m.content for m in b.messages] == ["show me shoes"]  # NOT a's message


def test_history_persists_across_instances(tmp_path):
    from langchain_community.chat_message_histories import SQLChatMessageHistory

    conn = f"sqlite:///{tmp_path / 'hist.db'}"
    first = SQLChatMessageHistory(session_id="user-a", connection=conn)
    first.add_user_message("remember this")

    # Simulate a process restart / different replica: brand-new instance, same store.
    reopened = SQLChatMessageHistory(session_id="user-a", connection=conn)
    assert [m.content for m in reopened.messages] == ["remember this"]
