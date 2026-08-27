"""上下文预算：窗口 / 输出预留 / 水位，以及单次请求的投影元数据。

对应 FirstCoder FC:9.2 的 ``context/token_budget.py``，按本仓库的产品决策
（M6 第 4 节）调整：
- 默认窗口 32k（``CODING_AGENT_CONTEXT_WINDOW`` 可覆盖，产品决策 #1）；
- 输出预留 4k 常量（产品决策 #2）；
- 不做 FC 的 ``usable_window = window * 0.95`` 折扣——我们直接用窗口当输入预算，
  因为 32k 已是保守默认，且需要让用户可预期（窗口即输入上限）；
- 水位 L1=70% / L2=85%（相对 input_capacity），L3=95% 由 Stage 4 直接判定，
  本阶段只暴露低/高水位区间。

预算只用于「判断当前投影是否逼近上限」，绝不修改 Session 事实（压缩只影响视图）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from coding_agent.context.estimator import (
    estimate_message_tokens,
    estimate_tool_definition_tokens,
)
from coding_agent.protocol import ToolDefinition
from coding_agent.session import SessionSnapshot

DEFAULT_CONTEXT_WINDOW = 32_768
DEFAULT_OUTPUT_RESERVE = 4_096
WATERMARK_L2 = 0.85
WATERMARK_L1 = 0.70


class ContextProjectionLevel(StrEnum):
    """当前投影所处的预算水位区间。

    - ``L0``：预算充足（input_tokens < L1 水位），直接投影全部事实；
    - ``L1``：进入压缩候选区（L1 ≤ input_tokens < L2），超长 ToolResult 可压缩
      （Stage 4 实现，本阶段只暴露信号）；
    - ``L2``：超过高水位（input_tokens ≥ L2），需要轮次淘汰 / 更强的压缩
      （Stage 4 实现，本阶段只暴露信号）。
    """

    L0 = "l0"
    L1 = "l1"
    L2 = "l2"


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """一次请求的预算快照。

    - ``context_window``：解析后的上下文窗口（token）；
    - ``output_reserve``：为输出预留的 token，输入预算要扣除；
    - ``input_capacity``：可用的输入 token 预算（= window - reserve）；
    - ``fixed_tokens``：system guidance + tools schema 的估算 token；
    - ``history_tokens``：SessionSnapshot 事实的估算 token；
    - ``input_tokens``：本次请求的总输入估算（= fixed + history）；
    - ``high_watermark``：L2 水位（input_capacity * 0.85）；
    - ``low_watermark``：L1 水位（input_capacity * 0.70）；
    - ``source``：窗口来自显式配置（configured）还是默认假设（assumed）。
    """

    context_window: int
    output_reserve: int
    input_capacity: int
    fixed_tokens: int
    history_tokens: int
    input_tokens: int
    high_watermark: int
    low_watermark: int
    source: str

    @property
    def level(self) -> ContextProjectionLevel:
        """按 input_tokens 判定当前水位区间。"""
        if self.input_tokens < self.low_watermark:
            return ContextProjectionLevel.L0
        if self.input_tokens < self.high_watermark:
            return ContextProjectionLevel.L1
        return ContextProjectionLevel.L2


@dataclass(frozen=True, slots=True)
class ContextProjection:
    """单次 ``build`` 的可观察产物（Stage 5 可观测性的原料）。

    ``ContextBuilder.build`` 的返回类型保持 ``ModelRequest`` 不变，projection 通过
    builder 的 ``last_projection`` 属性暴露，loop 不需要改签名。
    """

    session_id: str
    level: ContextProjectionLevel
    budget: ContextBudget
    messages_projected: int
    facts_count: int
    needs_compaction: bool
    suggested_level: ContextProjectionLevel | None
    compacted_tool_results: int = 0
    evicted_turn_ids: tuple[str, ...] = ()
    budget_exceeded: bool = False

    def to_event_payload(self) -> dict[str, object]:
        """转成 ``RuntimeEventKind.CONTEXT_PROJECTED`` 事件的 payload。

        供 AgentLoop 暴露预算状态（Stage 5 可观测性原料），context 包不依赖 runtime。
        """
        budget = self.budget
        return {
            "level": self.level.value,
            "input_tokens": budget.input_tokens,
            "input_capacity": budget.input_capacity,
            "low_watermark": budget.low_watermark,
            "high_watermark": budget.high_watermark,
            "needs_compaction": self.needs_compaction,
            "suggested_level": self.suggested_level.value if self.suggested_level else None,
            "source": budget.source,
            "messages_projected": self.messages_projected,
            "compacted_tool_results": self.compacted_tool_results,
            "evicted_turn_count": len(self.evicted_turn_ids),
            "budget_exceeded": self.budget_exceeded,
        }


def build_context_budget(
    *,
    snapshot: SessionSnapshot,
    tools: tuple[ToolDefinition, ...],
    context_window: int | None,
    max_output_tokens: int | None,
    system_tokens: int,
) -> ContextBudget:
    """计算一次请求的 ContextBudget。

    - ``resolved_window``：context_window 或 32_768；非 None 视为显式配置；
    - ``output_reserve``：max_output_tokens 或 4096；
    - ``usable_window``：直接用 resolved_window（不做 0.95 折扣，见模块 docstring）；
    - ``input_capacity``：usable_window - output_reserve；
    - ``fixed_tokens``：system_tokens + tools schema 估算；
    - ``history_tokens``：snapshot.messages 估算；
    - ``input_tokens``：fixed + history。

    window / reserve 必须为正数，且 reserve 必须为窗口保留输入容量。L1 水位必须
    严格小于 L2 水位，否则 ValueError。
    """
    if context_window is not None and context_window < 1:
        raise ValueError("context_window must be positive")
    if max_output_tokens is not None and max_output_tokens < 1:
        raise ValueError("max_output_tokens must be positive")

    resolved_window = context_window if context_window is not None else DEFAULT_CONTEXT_WINDOW
    output_reserve = max_output_tokens if max_output_tokens is not None else DEFAULT_OUTPUT_RESERVE
    usable_window = resolved_window
    input_capacity = usable_window - output_reserve
    if input_capacity < 1:
        raise ValueError("output_reserve must leave positive input_capacity")

    fixed_tokens = system_tokens + sum(estimate_tool_definition_tokens(tool) for tool in tools)
    history_tokens = sum(estimate_message_tokens(message) for message in snapshot.messages)
    input_tokens = fixed_tokens + history_tokens

    high_watermark = int(input_capacity * WATERMARK_L2)
    low_watermark = int(input_capacity * WATERMARK_L1)
    if low_watermark >= high_watermark:
        raise ValueError("low_watermark must be lower than high_watermark")

    source = "configured" if context_window is not None else "assumed"
    return ContextBudget(
        context_window=resolved_window,
        output_reserve=output_reserve,
        input_capacity=input_capacity,
        fixed_tokens=fixed_tokens,
        history_tokens=history_tokens,
        input_tokens=input_tokens,
        high_watermark=high_watermark,
        low_watermark=low_watermark,
        source=source,
    )
