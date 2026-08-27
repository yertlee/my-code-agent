"""BudgetedContextBuilder 的投影单元测试。

覆盖：L0 全量投影、L1/L2 信号暴露、projection 元数据正确、环境变量窗口覆盖、
以及 loop 的 CONTEXT_PROJECTED 事件暴露。
"""

from __future__ import annotations

import pytest

from coding_agent.context import (
    DEFAULT_CONTEXT_WINDOW,
    BudgetedContextBuilder,
    ContextProjectionLevel,
)
from coding_agent.protocol import ModelMessage, TokenUsage, ToolCall, ToolResult
from coding_agent.session import (
    SessionSnapshot,
    assistant_message,
    tool_result_message,
    user_message,
)


def _snapshot(session_id: str = "ses_1") -> SessionSnapshot:
    return SessionSnapshot(
        session_id=session_id,
        messages=(user_message(session_id, "question", turn_id="turn_1"),),
        usage=TokenUsage(),
    )


def _long_tool_snapshot(n_chars: int, session_id: str = "ses_1") -> SessionSnapshot:
    call = ToolCall("call_1", "Read", '{"path":"big.txt"}')
    result = ToolResult(
        tool_call_id="call_1",
        tool_name="Read",
        content="x" * n_chars,
    )
    return SessionSnapshot(
        session_id=session_id,
        messages=(
            user_message(session_id, "read big.txt", turn_id="turn_1"),
            assistant_message(session_id, turn_id="turn_1", text=None, tool_calls=(call,)),
            tool_result_message(session_id, result, turn_id="turn_1"),
            assistant_message(session_id, turn_id="turn_1", text="done"),
        ),
        usage=TokenUsage(),
    )


def test_budgeted_builder_projects_all_facts_under_low_watermark() -> None:
    builder = BudgetedContextBuilder()
    request = builder.build(model="demo", snapshot=_snapshot(), tools=())

    assert request.messages[0].role == "system"
    assert request.messages[1:] == (ModelMessage(role="user", content="question"),)


def test_budgeted_builder_l0_reports_no_compaction() -> None:
    builder = BudgetedContextBuilder()
    builder.build(model="demo", snapshot=_snapshot(), tools=())

    projection = builder.last_projection
    assert projection is not None
    assert projection.session_id == "ses_1"
    assert projection.level is ContextProjectionLevel.L0
    assert projection.needs_compaction is False
    assert projection.suggested_level is None
    assert projection.facts_count == 1
    assert projection.messages_projected == 2  # system + user


def test_budgeted_builder_enters_l1_when_history_is_large() -> None:
    # 单条 80k 字符的 tool result → 20k token，落在 L1 水位区间（20,070 ≤ input < 24,371）
    builder = BudgetedContextBuilder()
    request = builder.build(
        model="demo",
        snapshot=_long_tool_snapshot(80_000),
        tools=(),
    )

    projection = builder.last_projection
    assert projection is not None
    assert projection.level is ContextProjectionLevel.L1
    assert projection.needs_compaction is True
    assert projection.suggested_level is ContextProjectionLevel.L1
    # L1 仍投影全部事实（Stage 4 才压缩）
    assert request.messages[-1].role == "assistant"
    assert request.messages[-2].role == "tool"
    assert "x" * 80_000 in (request.messages[-2].content or "")


def test_budgeted_builder_enters_l2_above_high_watermark() -> None:
    # 100k 字符 → 25k token，超过 L2 水位（24,371）
    builder = BudgetedContextBuilder()
    builder.build(model="demo", snapshot=_long_tool_snapshot(100_000), tools=())

    projection = builder.last_projection
    assert projection is not None
    assert projection.level is ContextProjectionLevel.L2
    assert projection.needs_compaction is True
    assert projection.suggested_level is ContextProjectionLevel.L2


def test_budgeted_builder_honors_configured_window_for_levels() -> None:
    # 窗口 4k / 预留 1k → input_capacity 3k → low=2100, high=2550
    builder = BudgetedContextBuilder(context_window=4_000, max_output_tokens=1_000)
    builder.build(model="demo", snapshot=_long_tool_snapshot(20_000), tools=())

    projection = builder.last_projection
    assert projection is not None
    assert projection.budget.source == "configured"
    assert projection.budget.input_capacity == 3_000
    # 20k 字符 → 5k token，超过 high=2550
    assert projection.level is ContextProjectionLevel.L2


def test_budgeted_builder_estimate_injection_affects_budget() -> None:
    builder = BudgetedContextBuilder(estimate_text_tokens=lambda text: len(text) * 100)
    builder.build(model="demo", snapshot=_snapshot(), tools=())

    projection = builder.last_projection
    assert projection is not None
    assert projection.budget.fixed_tokens > DEFAULT_CONTEXT_WINDOW  # system 被放大


def test_budgeted_builder_satisfies_context_builder_protocol() -> None:
    from typing import get_type_hints

    hints = get_type_hints(BudgetedContextBuilder.build)
    assert hints["model"] is str
    assert "snapshot" in hints
    assert "tools" in hints


@pytest.mark.asyncio
async def test_agent_loop_emits_context_projected_event() -> None:
    from coding_agent.agent import AgentLoop
    from coding_agent.permissions import PermissionManager
    from coding_agent.providers import FakeProvider
    from coding_agent.runtime import RecordingEventSink, RuntimeEventKind
    from coding_agent.session import InMemorySessionStore
    from coding_agent.tools import ToolContext, ToolRegistry
    from coding_agent.workspace import Workspace

    store = InMemorySessionStore()
    events = RecordingEventSink()
    loop = AgentLoop(
        provider=FakeProvider(response_text="ok", repeat=True),
        model="fake-model",
        session_store=store,
        context_builder=BudgetedContextBuilder(),
        permission_manager=PermissionManager(),
        tool_context=ToolContext(Workspace(".")),
        tools=ToolRegistry(),
        event_sink=events,
    )

    await loop.run("hello")

    projected = [
        event for event in events.events if event.kind is RuntimeEventKind.CONTEXT_PROJECTED
    ]
    assert len(projected) == 1
    payload = projected[0].payload
    assert payload["level"] == "l0"
    assert payload["needs_compaction"] is False
    assert payload["input_capacity"] == 32_768 - 4_096
    assert payload["source"] == "assumed"
