from __future__ import annotations

from pathlib import Path

import pytest

from coding_agent.context import BasicContextBuilder
from coding_agent.memory import MemoryProjection
from coding_agent.permissions import PermissionVerdict, ReadOnlyPermissionPolicy
from coding_agent.protocol import ModelMessage, TokenUsage, ToolCall
from coding_agent.runtime import AgentCancelledError, CancellationToken
from coding_agent.session import InMemorySessionStore, SessionSnapshot


def test_in_memory_session_keeps_turns_messages_and_usage() -> None:
    store = InMemorySessionStore()
    first = store.begin_turn("first")
    store.append_message(first.session_id, ModelMessage(role="assistant", content="ack"))
    store.add_usage(first.session_id, TokenUsage(input_tokens=2, output_tokens=1, total_tokens=3))
    second = store.begin_turn("second", session_id=first.session_id)

    snapshot = store.snapshot(first.session_id)

    assert second.session_id == first.session_id
    assert second.turn_id != first.turn_id
    assert [message.content for message in snapshot.messages] == ["first", "ack", "second"]
    assert snapshot.usage.total_tokens == 3


class StaticMemoryRetriever:
    def retrieve(
        self,
        *,
        snapshot: SessionSnapshot,
        workspace_root: Path,
    ) -> MemoryProjection:
        assert snapshot.messages[-1].content == "question"
        assert workspace_root.name == "project"
        return MemoryProjection(("Use Python 3.12.",))


def test_basic_context_builder_projects_system_memory_and_session(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    store = InMemorySessionStore()
    turn = store.begin_turn("question")
    builder = BasicContextBuilder(
        workspace_root=workspace,
        memory=StaticMemoryRetriever(),
    )

    request = builder.build(
        model="demo",
        snapshot=store.snapshot(turn.session_id),
        tools=(),
    )

    assert request.messages[0].role == "system"
    assert "Relevant memory:\nUse Python 3.12." in (request.messages[0].content or "")
    assert request.messages[1] == ModelMessage(role="user", content="question")


def test_read_only_permission_policy_has_explicit_allow_and_deny() -> None:
    policy = ReadOnlyPermissionPolicy()

    allowed = policy.decide(ToolCall("read", "Read", "{}"))
    denied = policy.decide(ToolCall("edit", "Edit", "{}"))

    assert allowed.verdict is PermissionVerdict.ALLOW
    assert denied.verdict is PermissionVerdict.DENY
    assert "read-only mode" in denied.reason


def test_cancellation_token_is_cooperative_and_idempotent() -> None:
    token = CancellationToken()
    token.raise_if_cancelled()

    token.cancel()
    token.cancel()

    assert token.is_cancelled is True
    with pytest.raises(AgentCancelledError, match="cancelled"):
        token.raise_if_cancelled()
