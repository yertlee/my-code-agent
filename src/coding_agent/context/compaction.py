"""确定性的 Context 投影压缩。

压缩输入是 Session 事实的临时视图，返回的也是临时视图；调用方不得将结果写回
SessionStore。这里不访问工作区、不调用模型，因此同一份事实总会得到同一份投影。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from coding_agent.context.budget import ContextBudget
from coding_agent.context.estimator import estimate_message_tokens
from coding_agent.session import AgentMessage, MessagePart, PartKind, SessionSnapshot

TOOL_RESULT_FRACTION = 0.20
_MUTATION_TOOLS = frozenset({"Edit", "Write", "Delete"})


class ToolResultLifecycle(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    SUPERSEDED = "superseded"
    DERIVED = "derived"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class CompactionResult:
    """压缩后的临时事实视图及其可观察摘要。"""

    messages: tuple[AgentMessage, ...]
    budget: ContextBudget
    lifecycles: dict[str, ToolResultLifecycle]
    compacted_tool_results: int
    evicted_turn_ids: tuple[str, ...]
    budget_exceeded: bool


class ContextCompactor:
    """实现 L1（工具输出）与 L2（完整工作轮次）的确定性压缩。"""

    def compact(self, snapshot: SessionSnapshot, budget: ContextBudget) -> CompactionResult:
        lifecycles = classify_tool_result_lifecycles(snapshot.messages)
        max_result_tokens = max(1, int(budget.input_capacity * TOOL_RESULT_FRACTION))
        l1_messages, compacted = _compact_tool_results(
            snapshot.messages,
            max_result_tokens=max_result_tokens,
        )
        compacted_budget = _budget_for_messages(budget, l1_messages)
        evicted_turn_ids: tuple[str, ...] = ()
        if compacted_budget.input_tokens >= compacted_budget.high_watermark:
            l1_messages, evicted_turn_ids = _evict_old_turns(l1_messages, compacted_budget)
            compacted_budget = _budget_for_messages(budget, l1_messages)
        return CompactionResult(
            messages=l1_messages,
            budget=compacted_budget,
            lifecycles=lifecycles,
            compacted_tool_results=compacted,
            evicted_turn_ids=evicted_turn_ids,
            budget_exceeded=compacted_budget.input_tokens > compacted_budget.input_capacity,
        )


def classify_tool_result_lifecycles(
    messages: tuple[AgentMessage, ...],
) -> dict[str, ToolResultLifecycle]:
    """基于事实顺序与 metadata 分类 ToolResult，不读取文件系统。

    同一路径的较新读取覆盖旧读取；修改后的旧读取失效；Shell 输出属于可重建派生
    信息；相同内容的后续结果标记为重复。分类只作为压缩解释与后续策略输入，L1/L2
    不会因分类破坏工具调用和结果的配对。
    """
    results = [
        (message, part)
        for message in messages
        for part in message.parts
        if part.kind is PartKind.TOOL_RESULT
    ]
    lifecycles = {part.id: ToolResultLifecycle.FRESH for _, part in results}
    latest_read_by_path: dict[str, str] = {}
    seen_content: dict[str, str] = {}
    read_result_ids: set[str] = set()
    for _, part in results:
        tool_name = _metadata_string(part, "tool_name")
        path = _metadata_string(part, "path")
        content = part.content or ""
        if tool_name in _MUTATION_TOOLS:
            for result_part_id in read_result_ids:
                if lifecycles[result_part_id] is ToolResultLifecycle.FRESH:
                    lifecycles[result_part_id] = ToolResultLifecycle.STALE
            continue
        if tool_name == "Shell":
            lifecycles[part.id] = ToolResultLifecycle.DERIVED
        if tool_name == "Read" and path:
            previous = latest_read_by_path.get(path)
            if previous is not None:
                lifecycles[previous] = ToolResultLifecycle.SUPERSEDED
            latest_read_by_path[path] = part.id
            read_result_ids.add(part.id)
        if content:
            previous = seen_content.get(content)
            if previous is not None and lifecycles[part.id] is ToolResultLifecycle.FRESH:
                lifecycles[part.id] = ToolResultLifecycle.DUPLICATE
            else:
                seen_content[content] = part.id
    return lifecycles


def _compact_tool_results(
    messages: tuple[AgentMessage, ...],
    *,
    max_result_tokens: int,
) -> tuple[tuple[AgentMessage, ...], int]:
    compacted = 0
    output: list[AgentMessage] = []
    for message in messages:
        parts: list[MessagePart] = []
        changed = False
        for part in message.parts:
            if part.kind is PartKind.TOOL_RESULT and part.content is not None:
                content = compact_tool_result_content(part.content, max_result_tokens)
                if content != part.content:
                    part = replace(part, content=content)
                    compacted += 1
                    changed = True
            parts.append(part)
        output.append(replace(message, parts=tuple(parts)) if changed else message)
    return tuple(output), compacted


def compact_tool_result_content(content: str, max_tokens: int) -> str:
    """按字符近似将单条工具输出压到上限内，保留首尾证据。"""
    max_chars = max_tokens * 4
    if len(content) <= max_chars:
        return content
    omitted = len(content) - max_chars
    marker = f"\n… [tool output compacted: {omitted} chars omitted] …\n"
    available = max(2, max_chars - len(marker))
    head_chars = available // 2
    tail_chars = available - head_chars
    omitted = len(content) - head_chars - tail_chars
    marker = f"\n… [tool output compacted: {omitted} chars omitted] …\n"
    return content[:head_chars] + marker + content[-tail_chars:]


def _evict_old_turns(
    messages: tuple[AgentMessage, ...],
    budget: ContextBudget,
) -> tuple[tuple[AgentMessage, ...], tuple[str, ...]]:
    turn_ids = _turn_ids_in_order(messages)
    protected = _protected_turn_ids(messages, turn_ids)
    retained = list(messages)
    evicted: list[str] = []
    for turn_id in turn_ids:
        if turn_id in protected:
            continue
        candidate = tuple(message for message in retained if message.turn_id != turn_id)
        candidate_budget = _budget_for_messages(budget, candidate)
        retained = list(candidate)
        evicted.append(turn_id)
        if candidate_budget.input_tokens < candidate_budget.high_watermark:
            break
    return tuple(retained), tuple(evicted)


def _protected_turn_ids(
    messages: tuple[AgentMessage, ...],
    turn_ids: tuple[str, ...],
) -> frozenset[str]:
    if not turn_ids:
        return frozenset()
    protected = {turn_ids[-1]}
    mutation_index: int | None = None
    for index, message in enumerate(messages):
        if any(
            part.kind is PartKind.TOOL_RESULT
            and _metadata_string(part, "tool_name") in _MUTATION_TOOLS
            for part in message.parts
        ):
            mutation_index = index
    if mutation_index is not None:
        protected.update(message.turn_id for message in messages[mutation_index:])
    return frozenset(protected)


def _turn_ids_in_order(messages: tuple[AgentMessage, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(message.turn_id for message in messages))


def _budget_for_messages(
    budget: ContextBudget,
    messages: tuple[AgentMessage, ...],
) -> ContextBudget:
    history_tokens = sum(estimate_message_tokens(message) for message in messages)
    return replace(
        budget,
        history_tokens=history_tokens,
        input_tokens=budget.fixed_tokens + history_tokens,
    )


def _metadata_string(part: MessagePart, key: str) -> str | None:
    value = part.metadata.get(key)
    return value if isinstance(value, str) else None
