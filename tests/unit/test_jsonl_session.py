from __future__ import annotations

import json
from pathlib import Path

import pytest

from coding_agent.permissions import PermissionAction, PermissionRequest
from coding_agent.protocol import ModelMessage, TokenUsage, ToolCall
from coding_agent.session import (
    JsonlSessionStore,
    PendingPermission,
    SessionError,
)


def test_jsonl_replays_messages_usage_pending_and_claim(tmp_path: Path) -> None:
    store = JsonlSessionStore(tmp_path)
    identity = store.begin_turn("change demo")
    call = ToolCall("edit_1", "Edit", '{"path":"demo.py"}')
    store.append_message(
        identity.session_id,
        ModelMessage("assistant", tool_calls=(call,)),
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

    assert snapshot.messages[0] == ModelMessage("user", "change demo")
    assert snapshot.messages[1].tool_calls == (call,)
    assert snapshot.usage == TokenUsage(10, 4, 14)
    assert restored == pending
    assert reopened.list_sessions()[0]["status"] == "waiting"

    assert reopened.claim_pending("perm_1", "allow_once") == pending
    assert reopened.pending_for_session(identity.session_id) is None
    assert reopened.list_sessions()[0]["status"] == "ready"

    events = [
        json.loads(line)["kind"]
        for line in (tmp_path / f"{identity.session_id}.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
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
        handle.write(b'{"schema_version":1')

    assert JsonlSessionStore(tmp_path).snapshot(identity.session_id).messages == (
        ModelMessage("user", "hello"),
    )
    store.add_usage(identity.session_id, TokenUsage(2, 1, 3))
    assert JsonlSessionStore(tmp_path).snapshot(identity.session_id).usage.total_tokens == 3

    corrupt_identity = store.begin_turn("corrupt me")
    corrupt_path = tmp_path / f"{corrupt_identity.session_id}.jsonl"
    with corrupt_path.open("ab") as handle:
        handle.write(b"not-json\n")
    with pytest.raises(SessionError, match="line 2") as raised:
        JsonlSessionStore(tmp_path).snapshot(corrupt_identity.session_id)
    assert raised.value.code == "corrupt_session"
