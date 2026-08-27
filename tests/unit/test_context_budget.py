"""ContextBudget / TokenEstimator 的单元测试。

覆盖：字符近似、消息/工具/snapshot 估算、预算计算（窗口/水位/校验）、水位区间判定。
"""

from __future__ import annotations

import pytest

from coding_agent.context import (
    ContextBudget,
    ContextProjectionLevel,
    build_context_budget,
    estimate_message_tokens,
    estimate_snapshot_tokens,
    estimate_text_tokens,
    estimate_tool_definition_tokens,
)
from coding_agent.protocol import TokenUsage, ToolCall, ToolDefinition, ToolResult
from coding_agent.session import (
    SessionSnapshot,
    assistant_message,
    tool_result_message,
    user_message,
)


def test_estimate_text_tokens_uses_char_fourth_approximation() -> None:
    assert estimate_text_tokens("") == 1  # 下限为 1
    assert estimate_text_tokens("abcd") == 1
    assert estimate_text_tokens("a" * 100) == 25
    assert estimate_text_tokens("a" * 101) == 26
    assert estimate_text_tokens("a" * 4) == 1
    assert estimate_text_tokens("a" * 5) == 2


def test_estimate_message_tokens_covers_user_assistant_tool() -> None:
    user = user_message("ses_1", "hello", turn_id="turn_1")
    assert estimate_message_tokens(user) == (5 + 3) // 4 + 1  # 3

    assistant = assistant_message("ses_1", turn_id="turn_1", text="hi", reasoning_content="think")
    # reasoning + 正文 共 5 字符 → 2 token + 1 消息开销
    assert estimate_message_tokens(assistant) == 3

    call = ToolCall("call_1", "Grep", '{"query":"Target"}')
    assistant_with_call = assistant_message(
        "ses_1",
        turn_id="turn_1",
        text=None,
        tool_calls=(call,),
    )
    # arguments_json 17 字符 → 5 token + 1 消息开销
    assert estimate_message_tokens(assistant_with_call) == 6

    result = ToolResult(tool_call_id="call_1", tool_name="Grep", content="result text")
    tool = tool_result_message("ses_1", result, turn_id="turn_1")
    assert estimate_message_tokens(tool) == (11 + 3) // 4 + 1  # 4


def test_estimate_message_tokens_rejects_unknown_role() -> None:
    snapshot = SessionSnapshot(
        session_id="ses_1",
        messages=(user_message("ses_1", "q", turn_id="turn_1"),),
        usage=TokenUsage(),
    )
    weird = snapshot.messages[0]
    from dataclasses import replace

    with pytest.raises(ValueError, match="unknown fact message role"):
        estimate_message_tokens(replace(weird, role="system"))


def test_estimate_tool_definition_tokens_sums_schema_chars() -> None:
    tool = ToolDefinition(name="Grep", description="search files", input_schema={})
    # name 4 + description 12 + json "{}" 2 = 18 字符 → (18+3)//4 = 5
    assert estimate_tool_definition_tokens(tool) == 5


def test_estimate_snapshot_tokens_combines_history_and_tools() -> None:
    snapshot = SessionSnapshot(
        session_id="ses_1",
        messages=(
            user_message("ses_1", "hello", turn_id="turn_1"),
            assistant_message("ses_1", turn_id="turn_1", text="hi"),
        ),
        usage=TokenUsage(),
    )
    tools = (ToolDefinition(name="Grep", description="search", input_schema={}),)
    history = estimate_message_tokens(snapshot.messages[0]) + estimate_message_tokens(
        snapshot.messages[1]
    )
    schema = estimate_tool_definition_tokens(tools[0])
    assert estimate_snapshot_tokens(snapshot, tools) == history + schema


def _empty_snapshot(session_id: str = "ses_1") -> SessionSnapshot:
    return SessionSnapshot(session_id=session_id, messages=(), usage=TokenUsage())


def test_build_context_budget_defaults_to_32k_and_4k_reserve() -> None:
    budget = build_context_budget(
        snapshot=_empty_snapshot(),
        tools=(),
        context_window=None,
        max_output_tokens=None,
        system_tokens=101,
    )
    assert budget.context_window == 32_768
    assert budget.output_reserve == 4_096
    assert budget.input_capacity == 32_768 - 4_096
    assert budget.fixed_tokens == 101
    assert budget.history_tokens == 0
    assert budget.input_tokens == 101
    assert budget.high_watermark == int(budget.input_capacity * 0.85)
    assert budget.low_watermark == int(budget.input_capacity * 0.70)
    assert budget.low_watermark < budget.high_watermark
    assert budget.source == "assumed"


def test_build_context_budget_configured_window_is_marked() -> None:
    budget = build_context_budget(
        snapshot=_empty_snapshot(),
        tools=(),
        context_window=16_384,
        max_output_tokens=2_048,
        system_tokens=100,
    )
    assert budget.context_window == 16_384
    assert budget.output_reserve == 2_048
    assert budget.input_capacity == 16_384 - 2_048
    assert budget.high_watermark == int(budget.input_capacity * 0.85)
    assert budget.low_watermark == int(budget.input_capacity * 0.70)
    assert budget.source == "configured"


def test_build_context_budget_includes_tool_schema_in_fixed_tokens() -> None:
    tool = ToolDefinition(name="Read", description="read a file", input_schema={})
    budget = build_context_budget(
        snapshot=_empty_snapshot(),
        tools=(tool,),
        context_window=None,
        max_output_tokens=None,
        system_tokens=100,
    )
    assert budget.fixed_tokens == 100 + estimate_tool_definition_tokens(tool)


def test_build_context_budget_rejects_non_positive_window_or_reserve() -> None:
    with pytest.raises(ValueError, match="context_window must be positive"):
        build_context_budget(
            snapshot=_empty_snapshot(),
            tools=(),
            context_window=0,
            max_output_tokens=None,
            system_tokens=100,
        )
    with pytest.raises(ValueError, match="max_output_tokens must be positive"):
        build_context_budget(
            snapshot=_empty_snapshot(),
            tools=(),
            context_window=None,
            max_output_tokens=0,
            system_tokens=100,
        )


def test_build_context_budget_rejects_reserve_swallowing_window() -> None:
    with pytest.raises(ValueError, match="must leave positive"):
        build_context_budget(
            snapshot=_empty_snapshot(),
            tools=(),
            context_window=4096,
            max_output_tokens=4096,
            system_tokens=100,
        )


def test_build_context_budget_allows_large_output_reserve_with_input_room() -> None:
    budget = build_context_budget(
        snapshot=_empty_snapshot(),
        tools=(),
        context_window=8_192,
        max_output_tokens=6_144,
        system_tokens=100,
    )

    assert budget.input_capacity == 2_048


def test_build_context_budget_rejects_flat_watermarks() -> None:
    # window=3, reserve=1 → input_capacity=2 → low=int(1.4)=1, high=int(1.7)=1
    with pytest.raises(ValueError, match="low_watermark must be lower"):
        build_context_budget(
            snapshot=_empty_snapshot(),
            tools=(),
            context_window=3,
            max_output_tokens=1,
            system_tokens=100,
        )


def test_level_classifies_by_watermark_bands() -> None:
    low, high = 20_070, 24_371

    def budget(input_tokens: int) -> ContextBudget:
        return ContextBudget(
            context_window=32_768,
            output_reserve=4_096,
            input_capacity=28_672,
            fixed_tokens=101,
            history_tokens=0,
            input_tokens=input_tokens,
            high_watermark=high,
            low_watermark=low,
            source="assumed",
        )

    assert budget(low - 1).level is ContextProjectionLevel.L0
    assert budget(low).level is ContextProjectionLevel.L1
    assert budget(high - 1).level is ContextProjectionLevel.L1
    assert budget(high).level is ContextProjectionLevel.L2
