from __future__ import annotations

import pytest

from coding_agent.agent import AgentLoop
from coding_agent.context import (
    BudgetedContextBuilder,
    ContextCompactor,
    ToolResultLifecycle,
    build_context_budget,
    classify_tool_result_lifecycles,
    compact_tool_result_content,
)
from coding_agent.permissions import PermissionManager
from coding_agent.protocol import TokenUsage, ToolCall, ToolResult, TurnStatus
from coding_agent.providers import FakeProvider
from coding_agent.session import (
    InMemorySessionStore,
    SessionSnapshot,
    assistant_message,
    tool_result_message,
    user_message,
)
from coding_agent.tools import ToolContext, ToolRegistry
from coding_agent.workspace import Workspace


def _result(
    call_id: str,
    tool_name: str,
    content: str,
    *,
    path: str | None = None,
) -> ToolResult:
    metadata: dict[str, object] = {} if path is None else {"path": path}
    return ToolResult(call_id, tool_name, content, metadata=metadata)


def _snapshot(messages: tuple) -> SessionSnapshot:
    return SessionSnapshot("ses_1", messages, TokenUsage())


def test_lifecycle_classification_uses_only_fact_order_and_metadata() -> None:
    read_old = tool_result_message(
        "ses_1", _result("read_1", "Read", "before", path="demo.py"), turn_id="turn_1"
    )
    shell = tool_result_message(
        "ses_1", _result("shell_1", "Shell", "pytest output"), turn_id="turn_1"
    )
    edit = tool_result_message(
        "ses_1", _result("edit_1", "Edit", "updated", path="demo.py"), turn_id="turn_2"
    )
    read_new = tool_result_message(
        "ses_1", _result("read_2", "Read", "after", path="demo.py"), turn_id="turn_3"
    )
    duplicate = tool_result_message(
        "ses_1", _result("grep_1", "Grep", "after"), turn_id="turn_3"
    )

    lifecycles = classify_tool_result_lifecycles(
        (read_old, shell, edit, read_new, duplicate)
    )

    assert lifecycles[read_old.parts[0].id] is ToolResultLifecycle.SUPERSEDED
    assert lifecycles[shell.parts[0].id] is ToolResultLifecycle.DERIVED
    assert lifecycles[read_new.parts[0].id] is ToolResultLifecycle.FRESH
    assert lifecycles[duplicate.parts[0].id] is ToolResultLifecycle.DUPLICATE


def test_lifecycle_marks_read_before_mutation_stale() -> None:
    read = tool_result_message(
        "ses_1", _result("read_1", "Read", "before", path="demo.py"), turn_id="turn_1"
    )
    edit = tool_result_message(
        "ses_1", _result("edit_1", "Edit", "updated", path="demo.py"), turn_id="turn_2"
    )

    lifecycles = classify_tool_result_lifecycles((read, edit))

    assert lifecycles[read.parts[0].id] is ToolResultLifecycle.STALE


def test_l1_compaction_keeps_head_tail_and_explicit_marker() -> None:
    content = "A" * 80 + "middle" + "Z" * 80

    compacted = compact_tool_result_content(content, max_tokens=20)

    assert compacted.startswith("A")
    assert compacted.endswith("Z")
    assert "tool output compacted" in compacted
    assert len(compacted) <= len(content)


def test_l2_evicts_only_complete_old_turns() -> None:
    messages: list = []
    for turn_id, result_count in (("turn_1", 3), ("turn_2", 2)):
        messages.append(user_message("ses_1", f"task {turn_id}", turn_id=turn_id))
        calls = tuple(
            ToolCall(f"{turn_id}_{index}", "Read", '{"path":"big.txt"}')
            for index in range(result_count)
        )
        messages.append(assistant_message("ses_1", turn_id=turn_id, text=None, tool_calls=calls))
        messages.extend(
            tool_result_message(
                "ses_1",
                _result(call.id, "Read", "x" * 100_000, path="big.txt"),
                turn_id=turn_id,
            )
            for call in calls
        )
    messages.append(user_message("ses_1", "current task", turn_id="turn_3"))
    snapshot = _snapshot(tuple(messages))
    budget = build_context_budget(
        snapshot=snapshot,
        tools=(),
        context_window=32_768,
        max_output_tokens=4_096,
        system_tokens=100,
    )

    result = ContextCompactor().compact(snapshot, budget)

    assert result.compacted_tool_results == 5
    assert result.evicted_turn_ids == ("turn_1",)
    assert {message.turn_id for message in result.messages} == {"turn_2", "turn_3"}
    assert result.budget.input_tokens < result.budget.high_watermark


@pytest.mark.asyncio
async def test_l3_stops_before_provider_when_current_task_exceeds_capacity(tmp_path) -> None:
    provider = FakeProvider(response_text="must not run")
    loop = AgentLoop(
        provider=provider,
        model="fake-model",
        session_store=InMemorySessionStore(),
        context_builder=BudgetedContextBuilder(context_window=4_000, max_output_tokens=1_000),
        permission_manager=PermissionManager(),
        tool_context=ToolContext(Workspace(tmp_path)),
        tools=ToolRegistry(),
    )

    result = await loop.run("x" * 20_000)

    assert result.status is TurnStatus.LIMITED
    assert result.stop_reason == "context_budget_exceeded"
    assert provider.requests == []
