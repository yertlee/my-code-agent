from __future__ import annotations

from pathlib import Path

import pytest

from coding_agent.permissions import (
    PermissionAction,
    PermissionDecision,
    PermissionManager,
    PermissionMode,
    PermissionVerdict,
    permission_request,
)
from coding_agent.protocol import ToolCall, ToolResult
from coding_agent.tools import PreparedToolCall, ToolContext, ToolRegistry, coding_tools
from coding_agent.workspace import Workspace


def test_permission_modes_and_exact_path_session_grant(tmp_path: Path) -> None:
    target = str(tmp_path / "demo.py")
    request = permission_request(PermissionAction.WRITE, target, "edit")
    other = permission_request(PermissionAction.WRITE, str(tmp_path / "other.py"), "edit")

    standard = PermissionManager(mode=PermissionMode.STANDARD)
    assert standard.preflight(request).verdict is PermissionVerdict.ASK
    assert standard.resolve(request, "allow_session").verdict is PermissionVerdict.ALLOW
    assert standard.preflight(request).verdict is PermissionVerdict.ALLOW
    assert standard.preflight(other).verdict is PermissionVerdict.ASK

    plan = PermissionManager(mode=PermissionMode.PLAN)
    bypass = PermissionManager(mode=PermissionMode.BYPASS)
    assert plan.preflight(request).verdict is PermissionVerdict.DENY
    assert bypass.preflight(request).verdict is PermissionVerdict.ALLOW


def test_policy_deny_takes_precedence_over_existing_session_grant(tmp_path: Path) -> None:
    target = str(tmp_path / "demo.py")
    request = permission_request(PermissionAction.WRITE, target, "edit")
    manager = PermissionManager()
    assert manager.resolve(request, "allow_session").verdict is PermissionVerdict.ALLOW

    class DenyPolicy:
        def decide(
            self,
            request: object,
            *,
            mode: PermissionMode,
        ) -> PermissionDecision:
            del request, mode
            return PermissionDecision(PermissionVerdict.DENY, "hard policy deny")

    manager.policy = DenyPolicy()
    decision = manager.preflight(request)

    assert decision.verdict is PermissionVerdict.DENY
    assert decision.reason == "hard policy deny"


@pytest.mark.asyncio
async def test_edit_preview_execute_and_stale_snapshot(tmp_path: Path) -> None:
    target = tmp_path / "demo.py"
    target.write_text("value = 1\n", encoding="utf-8")
    context = ToolContext(Workspace(tmp_path))
    registry = ToolRegistry(coding_tools())
    call = ToolCall(
        "edit_1",
        "Edit",
        '{"operation":"replace","path":"demo.py","old_text":"1","new_text":"2"}',
    )

    prepared = await registry.prepare(call, context)
    assert isinstance(prepared, PreparedToolCall)
    assert prepared.preflight.preview is not None
    assert "-value = 1" in str(prepared.preflight.preview["diff"])
    result = await registry.execute_prepared(prepared, context)

    assert result.is_error is False
    assert target.read_text(encoding="utf-8") == "value = 2\n"

    stale_call = ToolCall(
        "edit_2",
        "Edit",
        '{"operation":"replace","path":"demo.py","old_text":"2","new_text":"3"}',
    )
    stale = await registry.prepare(stale_call, context)
    assert isinstance(stale, PreparedToolCall)
    target.write_text("external = True\n", encoding="utf-8")
    stale_result = await registry.execute_prepared(stale, context)

    assert stale_result.is_error is True
    assert "stale_snapshot" in stale_result.content
    assert target.read_text(encoding="utf-8") == "external = True\n"


@pytest.mark.asyncio
async def test_todo_revision_and_powershell_result(tmp_path: Path) -> None:
    context = ToolContext(Workspace(tmp_path))
    registry = ToolRegistry(coding_tools())
    todo = await registry.execute(
        ToolCall(
            "todo_1",
            "TodoWrite",
            '{"expected_revision":0,"items":[{"id":"a","content":"work","status":"in_progress"}]}',
        ),
        context,
    )
    conflict = await registry.execute(
        ToolCall("todo_2", "TodoWrite", '{"expected_revision":0,"items":[]}'),
        context,
    )

    shell_call = ToolCall(
        "shell_1",
        "Shell",
        '{"command":"Write-Output m4","timeout_seconds":10}',
    )
    shell = await registry.prepare(shell_call, context)
    assert isinstance(shell, PreparedToolCall)
    shell_result = await registry.execute_prepared(shell, context)

    assert "revision: 1" in todo.content
    assert conflict.is_error is True
    assert "revision_conflict" in conflict.content
    assert shell_result.is_error is False
    assert "m4" in shell_result.content
    assert "exit_code: 0" in shell_result.content


@pytest.mark.asyncio
async def test_direct_edit_execution_requires_prepared_approval(tmp_path: Path) -> None:
    context = ToolContext(Workspace(tmp_path))
    registry = ToolRegistry(coding_tools())
    result = await registry.execute(
        ToolCall(
            "edit",
            "Edit",
            '{"operation":"create","path":"new.py","new_text":"x = 1\\n"}',
        ),
        context,
    )

    assert isinstance(result, ToolResult)
    assert result.is_error is True
    assert "permission_required" in result.content
    assert not (tmp_path / "new.py").exists()


@pytest.mark.asyncio
async def test_powershell_timeout_is_bounded_and_reported(tmp_path: Path) -> None:
    context = ToolContext(Workspace(tmp_path))
    registry = ToolRegistry(coding_tools())
    call = ToolCall(
        "shell_timeout",
        "Shell",
        '{"command":"Start-Sleep -Seconds 5","timeout_seconds":0.1}',
    )
    prepared = await registry.prepare(call, context)
    assert isinstance(prepared, PreparedToolCall)

    result = await registry.execute_prepared(prepared, context)

    assert result.is_error is True
    assert result.metadata["timed_out"] is True
    assert "ERROR [timeout]" in result.content
