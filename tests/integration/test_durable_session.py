from __future__ import annotations

from pathlib import Path

import pytest

from coding_agent.app import build_application
from coding_agent.protocol import ToolCall, TurnStatus
from coding_agent.providers import FakeProvider, FakeResponse
from coding_agent.session import JsonlSessionStore, SessionError
from coding_agent.tools import ToolRegistry, coding_tools
from coding_agent.workspace import Workspace


def _edit_call() -> ToolCall:
    return ToolCall(
        "durable_edit",
        "Edit",
        '{"operation":"replace","path":"demo.py","old_text":"1","new_text":"2"}',
    )


@pytest.mark.asyncio
async def test_permission_wait_survives_process_restart_and_executes_once(
    tmp_path: Path,
) -> None:
    target = tmp_path / "demo.py"
    target.write_text("value = 1\n", encoding="utf-8")
    session_dir = tmp_path / "sessions"
    first = build_application(
        provider=FakeProvider(script=(FakeResponse(tool_calls=(_edit_call(),)),)),
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(coding_tools()),
        session_store=JsonlSessionStore(session_dir),
    )
    waiting = await first.run("change it")
    await first.aclose()

    assert waiting.status is TurnStatus.WAITING
    assert waiting.pending_input is not None
    assert target.read_text(encoding="utf-8") == "value = 1\n"

    resumed_provider = FakeProvider(script=(FakeResponse(text="changed"),))
    second = build_application(
        provider=resumed_provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(coding_tools()),
        session_store=JsonlSessionStore(session_dir),
    )
    pending = second.pending_permission(waiting.session_id)
    assert pending is not None
    assert pending == waiting.pending_input
    result = await second.resume_permission(pending.request_id, "allow_once")
    await second.aclose()

    assert result.status is TurnStatus.COMPLETED
    assert target.read_text(encoding="utf-8") == "value = 2\n"
    assert resumed_provider.requests[0].messages[-1].role == "tool"
    assert "replace completed" in (resumed_provider.requests[0].messages[-1].content or "")

    third = build_application(
        provider=FakeProvider(response_text="unused"),
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(coding_tools()),
        session_store=JsonlSessionStore(session_dir),
    )
    assert third.pending_permission(waiting.session_id) is None
    with pytest.raises(SessionError) as raised:
        await third.resume_permission(pending.request_id, "allow_once")
    await third.aclose()
    assert raised.value.code == "unknown_pending_permission"
    assert target.read_text(encoding="utf-8") == "value = 2\n"


@pytest.mark.asyncio
async def test_changed_preview_becomes_stale_tool_result_after_restart(tmp_path: Path) -> None:
    target = tmp_path / "demo.py"
    target.write_text("value = 1\n", encoding="utf-8")
    session_dir = tmp_path / "sessions"
    first = build_application(
        provider=FakeProvider(script=(FakeResponse(tool_calls=(_edit_call(),)),)),
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(coding_tools()),
        session_store=JsonlSessionStore(session_dir),
    )
    waiting = await first.run("change it")
    await first.aclose()
    assert waiting.pending_input is not None

    target.write_text("external = True\n", encoding="utf-8")
    provider = FakeProvider(script=(FakeResponse(text="stale explained"),))
    second = build_application(
        provider=provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(coding_tools()),
        session_store=JsonlSessionStore(session_dir),
    )
    result = await second.resume_permission(
        waiting.pending_input.request_id,
        "allow_once",
    )
    await second.aclose()

    assert result.status is TurnStatus.COMPLETED
    assert target.read_text(encoding="utf-8") == "external = True\n"
    assert "stale_snapshot" in (provider.requests[0].messages[-1].content or "")
