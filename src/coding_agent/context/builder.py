from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from coding_agent.context.budget import (
    ContextProjection,
    ContextProjectionLevel,
    build_context_budget,
)
from coding_agent.context.estimator import estimate_text_tokens
from coding_agent.protocol import ModelMessage, ModelRequest, ToolCall, ToolDefinition
from coding_agent.session import AgentMessage, MessagePart, PartKind, SessionSnapshot

SYSTEM_GUIDANCE = """You are a local coding agent operating inside one workspace.
Use repository tools when claims depend on local code.
Inspect relevant files before editing them.
Use Edit for file changes, Shell for commands and verification,
and TodoWrite for non-trivial task state.
Tool calls are validated and permission-gated by the runtime.
Never claim an action ran before its result.
Base completion claims on tool evidence. Paths in answers must be workspace-relative."""

EstimateTextTokens = Callable[[str], int]


class ContextBuilder(Protocol):
    def build(
        self,
        *,
        model: str,
        snapshot: SessionSnapshot,
        tools: tuple[ToolDefinition, ...],
    ) -> ModelRequest: ...


@dataclass(slots=True)
class BasicContextBuilder:
    system_guidance: str = SYSTEM_GUIDANCE

    def build(
        self,
        *,
        model: str,
        snapshot: SessionSnapshot,
        tools: tuple[ToolDefinition, ...],
    ) -> ModelRequest:
        messages = (
            ModelMessage(role="system", content=self.system_guidance),
            *facts_to_model_messages(snapshot),
        )
        return ModelRequest(model=model, messages=messages, tools=tools)


@dataclass(slots=True)
class BudgetedContextBuilder:
    """预算化投影：先算预算、判水位，再（保持）把事实投影成 ModelRequest。

    - 默认窗口 32k / 输出预留 4k，可用 ``context_window`` / ``max_output_tokens``
      覆盖（Stage 5 才接 CLI 参数，环境变量见 ``config`` / factory）。
    - 本阶段只做「预算判断 + 水位触发」：L0 直接投影全部；L1/L2 只暴露
      ``needs_compaction`` 信号，真正的压缩逻辑在 Stage 4 接入。
    - ``facts_to_model_messages`` 仍是唯一投影点；本类用它投影（可能被 Stage 4
      压缩的）事实。
    - 投影元数据通过 ``last_projection`` 暴露（Stage 5 可观测性原料），
      ``ModelRequest`` 结构不变。
    """

    system_guidance: str = SYSTEM_GUIDANCE
    context_window: int | None = None
    max_output_tokens: int | None = None
    estimate_text_tokens: EstimateTextTokens = estimate_text_tokens
    last_projection: ContextProjection | None = None

    def build(
        self,
        *,
        model: str,
        snapshot: SessionSnapshot,
        tools: tuple[ToolDefinition, ...],
    ) -> ModelRequest:
        system_tokens = self.estimate_text_tokens(self.system_guidance)
        budget = build_context_budget(
            snapshot=snapshot,
            tools=tools,
            context_window=self.context_window,
            max_output_tokens=self.max_output_tokens,
            system_tokens=system_tokens,
        )
        messages = (
            ModelMessage(role="system", content=self.system_guidance),
            *facts_to_model_messages(snapshot),
        )
        level = budget.level
        needs = level is not ContextProjectionLevel.L0
        self.last_projection = ContextProjection(
            session_id=snapshot.session_id,
            level=level,
            budget=budget,
            messages_projected=len(messages),
            facts_count=len(snapshot.messages),
            needs_compaction=needs,
            suggested_level=None if not needs else level,
        )
        return ModelRequest(model=model, messages=messages, tools=tools)


def facts_to_model_messages(snapshot: SessionSnapshot) -> tuple[ModelMessage, ...]:
    """把 Session 事实账本投影成 provider 请求用的 ModelMessage。

    这是「事实账本 → 请求格式」的唯一投影点。规则：
    - user 事实：文本 part 全部拼成一条 role=user 消息；
    - assistant 事实：推理 part、正文 part、tool_call part 合成一条 role=assistant
      消息（content + tool_calls）；工具调用以 tool_call part 携带的三要素重建；
    - tool 事实：tool_result part 投影成 role=tool 消息（tool_call_id + content）。
    """
    messages: list[ModelMessage] = []
    for message in snapshot.messages:
        if message.role == "user":
            content = _join_part_texts(message)
            if content is not None:
                messages.append(ModelMessage(role="user", content=content))
        elif message.role == "assistant":
            projected = _project_assistant(message)
            if projected is not None:
                messages.append(projected)
        elif message.role == "tool":
            for part in message.parts:
                if part.kind is not PartKind.TOOL_RESULT:
                    continue
                messages.append(
                    ModelMessage(
                        role="tool",
                        content=part.content,
                        tool_call_id=_str_or_none(part.metadata.get("tool_call_id")),
                    )
                )
        else:
            raise ValueError(f"unknown fact message role: {message.role}")
    return tuple(messages)


def _project_assistant(message: AgentMessage) -> ModelMessage | None:
    text_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for part in message.parts:
        if part.kind is PartKind.TOOL_CALL:
            tool_call = _tool_call_from_part(part)
            if tool_call is not None:
                tool_calls.append(tool_call)
        elif part.kind is PartKind.TEXT:
            if part.metadata.get("reasoning"):
                if part.content:
                    reasoning_parts.append(part.content)
            elif part.content:
                text_parts.append(part.content)
    content = "".join(text_parts) or None
    if content is None and not tool_calls and not reasoning_parts:
        return None
    return ModelMessage(
        role="assistant",
        content=content,
        tool_calls=tuple(tool_calls),
        reasoning_content="".join(reasoning_parts) or None,
    )


def _tool_call_from_part(part: MessagePart) -> ToolCall | None:
    call_id = _str_or_none(part.metadata.get("tool_call_id"))
    name = _str_or_none(part.metadata.get("tool_name"))
    arguments = _str_or_none(part.metadata.get("arguments_json"))
    if call_id is None or name is None:
        return None
    return ToolCall(call_id, name, arguments if arguments is not None else "{}")


def _join_part_texts(message: AgentMessage) -> str | None:
    texts = [part.content for part in message.parts if part.content]
    return "".join(texts) or None


def _str_or_none(value: object) -> str | None:
    return None if value is None else str(value)
