from __future__ import annotations

import json
from pathlib import Path

import pytest

from coding_agent.permissions import PermissionAction, PermissionRequest
from coding_agent.protocol import TokenUsage, ToolCall
from coding_agent.session import (
    JsonlSessionStore,
    PartKind,
    PendingPermission,
    SessionError,
    assistant_message,
)


def test_jsonl_replays_messages_usage_pending_and_claim(tmp_path: Path) -> None:
    store = JsonlSessionStore(tmp_path)
    identity = store.begin_turn("change demo")
    call = ToolCall("edit_1", "Edit", '{"path":"demo.py"}')
    store.append_message(
        identity.session_id,
        assistant_message(
            identity.session_id,
            turn_id=identity.turn_id,
            text=None,
            tool_calls=(call,),
        ),
    )
    store.add_usage(identity.session_id, TokenUsage(10, 4, 14))
    pending = PendingPermission(
        identity=identity,
        call=call,
        remaining_calls=(),
        request=PermissionRequest(
            "perm_1",
            PermissionAction.WRITE,
            str(tmp_path / "demo.py"),
            "edit demo.py",
            {"path": "demo.py"},
        ),
        preview={"operation": "replace"},
        confirmation_fingerprint="fingerprint",
        tools_used=(),
        usage=TokenUsage(10, 4, 14),
        model_calls=1,
        tool_rounds=1,
        last_output_text="",
    )
    store.save_pending(pending)

    reopened = JsonlSessionStore(tmp_path)
    snapshot = reopened.snapshot(identity.session_id)
    restored = reopened.pending_for_session(identity.session_id)

    user_fact = snapshot.messages[0]
    assert user_fact.role == "user"
    assert user_fact.turn_id == identity.turn_id
    assert user_fact.parts[0].kind is PartKind.TEXT
    assert user_fact.parts[0].content == "change demo"

    assistant_fact = snapshot.messages[1]
    assert assistant_fact.role == "assistant"
    assert assistant_fact.turn_id == identity.turn_id
    assert assistant_fact.parts[0].kind is PartKind.TOOL_CALL
    assert assistant_fact.parts[0].metadata["tool_call_id"] == call.id
    assert assistant_fact.parts[0].metadata["tool_name"] == call.name
    assert assistant_fact.parts[0].metadata["arguments_json"] == call.arguments_json

    assert snapshot.usage == TokenUsage(10, 4, 14)
    assert restored == pending
    assert reopened.list_sessions()[0]["status"] == "waiting"

    assert reopened.claim_pending("perm_1", "allow_once") == pending
    assert reopened.pending_for_session(identity.session_id) is None
    assert reopened.list_sessions()[0]["status"] == "ready"

    events = [
        json.loads(line)["kind"]
        for line in (tmp_path / f"{identity.session_id}.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert events == [
        "turn_started",
        "message_appended",
        "usage_added",
        "permission_pending",
        "permission_claimed",
    ]


def test_jsonl_ignores_partial_tail_and_reports_corrupt_complete_line(tmp_path: Path) -> None:
    store = JsonlSessionStore(tmp_path)
    identity = store.begin_turn("hello")
    path = tmp_path / f"{identity.session_id}.jsonl"
    with path.open("ab") as handle:
        handle.write(b'{"incomplete":')

    messages = JsonlSessionStore(tmp_path).snapshot(identity.session_id).messages
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].parts[0].content == "hello"
    store.add_usage(identity.session_id, TokenUsage(2, 1, 3))
    assert JsonlSessionStore(tmp_path).snapshot(identity.session_id).usage.total_tokens == 3

    corrupt_identity = store.begin_turn("corrupt me")
    corrupt_path = tmp_path / f"{corrupt_identity.session_id}.jsonl"
    with corrupt_path.open("ab") as handle:
        handle.write(b"not-json\n")
    with pytest.raises(SessionError, match="line 2") as raised:
        JsonlSessionStore(tmp_path).snapshot(corrupt_identity.session_id)
    assert raised.value.code == "corrupt_session"


@pytest.mark.parametrize("schema_version", (1, 2))
def test_jsonl_accepts_only_current_schema(tmp_path: Path, schema_version: int) -> None:
    store = JsonlSessionStore(tmp_path)
    identity = store.begin_turn("hello")
    path = tmp_path / f"{identity.session_id}.jsonl"
    unsupported_event = (
        '{"schema_version":'
        + str(schema_version)
        + ',"kind":"message_appended","session_id":"'
        + identity.session_id
        + '","payload":{"message":{"role":"assistant","content":"ack"}}}\n'
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(unsupported_event)

    with pytest.raises(SessionError, match="unsupported schema_version") as raised:
        JsonlSessionStore(tmp_path).snapshot(identity.session_id)
    assert raised.value.code == "corrupt_session"
