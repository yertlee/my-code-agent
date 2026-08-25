from __future__ import annotations

from pathlib import Path

import pytest

from coding_agent.app import build_application
from coding_agent.permissions import PermissionMode
from coding_agent.protocol import ToolCall, TurnStatus
from coding_agent.providers import FakeProvider, FakeResponse
from coding_agent.tools import ToolRegistry, coding_tools
from coding_agent.workspace import Workspace


def edit_call(call_id: str, old: str, new: str) -> ToolCall:
    return ToolCall(
        call_id,
        "Edit",
        f'{{"operation":"replace","path":"demo.py","old_text":"{old}","new_text":"{new}"}}',
    )


@pytest.mark.asyncio
async def test_standard_permission_pauses_and_resumes_trusted_edit(tmp_path: Path) -> None:
    target = tmp_path / "demo.py"
    target.write_text("value = 1\n", encoding="utf-8")
    provider = FakeProvider(
        script=(
            FakeResponse(tool_calls=(edit_call("edit", "1", "2"),)),
            FakeResponse(text="changed"),
        )
    )
    application = build_application(
        provider=provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(coding_tools()),
    )

    waiting = await application.run("change it")
    assert waiting.status is TurnStatus.WAITING
    assert waiting.pending_input is not None
    assert target.read_text(encoding="utf-8") == "value = 1\n"

    result = await application.resume_permission(
        waiting.pending_input.request_id,
        "allow_once",
    )
    await application.aclose()

    assert result.status is TurnStatus.COMPLETED
    assert target.read_text(encoding="utf-8") == "value = 2\n"
    assert "replace completed" in (provider.requests[1].messages[-1].content or "")


@pytest.mark.asyncio
async def test_stale_and_denied_edits_preserve_current_file(tmp_path: Path) -> None:
    target = tmp_path / "demo.py"
    target.write_text("value = 1\n", encoding="utf-8")
    stale_provider = FakeProvider(
        script=(
            FakeResponse(tool_calls=(edit_call("stale", "1", "2"),)),
            FakeResponse(text="stale handled"),
        )
    )
    stale_app = build_application(
        provider=stale_provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(coding_tools()),
    )
    waiting = await stale_app.run("change")
    assert waiting.pending_input is not None
    target.write_text("external = True\n", encoding="utf-8")
    result = await stale_app.resume_permission(waiting.pending_input.request_id, "allow_once")
    await stale_app.aclose()

    assert result.status is TurnStatus.COMPLETED
    assert target.read_text(encoding="utf-8") == "external = True\n"
    assert "stale_snapshot" in (stale_provider.requests[1].messages[-1].content or "")

    target.write_text("value = 1\n", encoding="utf-8")
    denied_provider = FakeProvider(
        script=(
            FakeResponse(tool_calls=(edit_call("denied", "1", "2"),)),
            FakeResponse(text="denied handled"),
        )
    )
    denied_app = build_application(
        provider=denied_provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(coding_tools()),
    )
    denied_waiting = await denied_app.run("change")
    assert denied_waiting.pending_input is not None
    await denied_app.resume_permission(denied_waiting.pending_input.request_id, "deny")
    await denied_app.aclose()
    assert target.read_text(encoding="utf-8") == "value = 1\n"


@pytest.mark.asyncio
async def test_plan_denies_and_bypass_applies_without_waiting(tmp_path: Path) -> None:
    target = tmp_path / "demo.py"
    target.write_text("value = 1\n", encoding="utf-8")
    plan_provider = FakeProvider(
        script=(
            FakeResponse(tool_calls=(edit_call("plan", "1", "2"),)),
            FakeResponse(text="planned"),
        )
    )
    plan_app = build_application(
        provider=plan_provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(coding_tools()),
        permission_mode=PermissionMode.PLAN,
    )
    plan_result = await plan_app.run("plan")
    await plan_app.aclose()
    assert plan_result.status is TurnStatus.COMPLETED
    assert target.read_text(encoding="utf-8") == "value = 1\n"

    bypass_provider = FakeProvider(
        script=(
            FakeResponse(tool_calls=(edit_call("bypass", "1", "2"),)),
            FakeResponse(text="changed"),
        )
    )
    bypass_app = build_application(
        provider=bypass_provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(coding_tools()),
        permission_mode=PermissionMode.BYPASS,
    )
    bypass_result = await bypass_app.run("change")
    await bypass_app.aclose()
    assert bypass_result.status is TurnStatus.COMPLETED
    assert target.read_text(encoding="utf-8") == "value = 2\n"


@pytest.mark.asyncio
async def test_edit_session_grant_allows_later_edit_to_exact_path(tmp_path: Path) -> None:
    target = tmp_path / "demo.py"
    target.write_text("value = 1\n", encoding="utf-8")
    provider = FakeProvider(
        script=(
            FakeResponse(tool_calls=(edit_call("first", "1", "2"),)),
            FakeResponse(tool_calls=(edit_call("second", "2", "3"),)),
            FakeResponse(text="changed twice"),
        )
    )
    application = build_application(
        provider=provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(coding_tools()),
    )

    waiting = await application.run("change twice")
    assert waiting.pending_input is not None
    result = await application.resume_permission(
        waiting.pending_input.request_id,
        "allow_session",
    )
    await application.aclose()

    assert result.status is TurnStatus.COMPLETED
    assert result.pending_input is None
    assert target.read_text(encoding="utf-8") == "value = 3\n"
