from __future__ import annotations

import pytest

from coding_agent.context import BasicContextBuilder
from coding_agent.protocol import ModelMessage, TokenUsage
from coding_agent.runtime import AgentCancelledError, CancellationToken
from coding_agent.session import InMemorySessionStore, assistant_message


def test_in_memory_session_keeps_turns_messages_and_usage() -> None:
    store = InMemorySessionStore()
    first = store.begin_turn("first")
    store.append_message(
        first.session_id,
        assistant_message(first.session_id, turn_id=first.turn_id, text="ack"),
    )
    store.add_usage(first.session_id, TokenUsage(input_tokens=2, output_tokens=1, total_tokens=3))
    second = store.begin_turn("second", session_id=first.session_id)

    snapshot = store.snapshot(first.session_id)

    assert second.session_id == first.session_id
    assert second.turn_id != first.turn_id
    assert [message.role for message in snapshot.messages] == ["user", "assistant", "user"]
    assert snapshot.messages[0].parts[0].content == "first"
    assert snapshot.messages[1].parts[0].content == "ack"
    assert snapshot.messages[2].parts[0].content == "second"
    assert snapshot.usage.total_tokens == 3


def test_basic_context_builder_projects_system_and_session() -> None:
    store = InMemorySessionStore()
    turn = store.begin_turn("question")
    builder = BasicContextBuilder()

    request = builder.build(
        model="demo",
        snapshot=store.snapshot(turn.session_id),
        tools=(),
    )

    assert request.messages[0].role == "system"
    assert "local coding agent" in (request.messages[0].content or "")
    assert request.messages[1] == ModelMessage(role="user", content="question")


def test_cancellation_token_is_cooperative_and_idempotent() -> None:
    token = CancellationToken()
    token.raise_if_cancelled()

    token.cancel()
    token.cancel()

    assert token.is_cancelled is True
    with pytest.raises(AgentCancelledError, match="cancelled"):
        token.raise_if_cancelled()
