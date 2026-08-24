from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import uuid4

from coding_agent.protocol import (
    ErrorInfo,
    ModelMessage,
    ModelRequest,
    ProviderError,
    ReasoningDelta,
    ResponseCompleted,
    TextDelta,
    TokenUsage,
    TurnResult,
    TurnStatus,
)
from coding_agent.providers.base import ChatProvider
from coding_agent.tools import ToolContext, ToolRegistry
from coding_agent.workspace import Workspace

SYSTEM_GUIDANCE = """You are a local coding agent with read-only repository tools.
Use tools when the answer depends on repository contents. Base repository claims on tool evidence.
Never claim to have read a file you did not inspect. Paths in answers must be workspace-relative."""


@dataclass(frozen=True, slots=True)
class RuntimeLimits:
    max_model_calls: int = 8
    max_tool_rounds: int = 6
    max_turn_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.max_model_calls < 1:
            raise ValueError("max_model_calls must be at least 1")
        if self.max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1")
        if self.max_turn_seconds <= 0:
            raise ValueError("max_turn_seconds must be positive")


@dataclass(slots=True)
class _RunState:
    session_id: str = field(default_factory=lambda: f"ses_{uuid4().hex}")
    turn_id: str = field(default_factory=lambda: f"turn_{uuid4().hex}")
    messages: list[ModelMessage] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    model_calls: int = 0
    tool_rounds: int = 0
    last_output_text: str = ""


class RuntimeRunner:
    def __init__(
        self,
        *,
        provider: ChatProvider,
        model: str,
        workspace: Workspace,
        tools: ToolRegistry,
        limits: RuntimeLimits | None = None,
        on_text_delta: Callable[[str], None] | None = None,
        on_tool_activity: Callable[[str, str], None] | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.tool_context = ToolContext(workspace=workspace)
        self.tools = tools
        self.limits = limits or RuntimeLimits()
        self.on_text_delta = on_text_delta
        self.on_tool_activity = on_tool_activity

    async def run(self, prompt: str) -> TurnResult:
        state = _RunState(
            messages=[
                ModelMessage(role="system", content=SYSTEM_GUIDANCE),
                ModelMessage(role="user", content=prompt),
            ]
        )
        try:
            async with asyncio.timeout(self.limits.max_turn_seconds):
                return await self._run_loop(state)
        except TimeoutError:
            return self._result(state, TurnStatus.LIMITED, "turn_timeout")
        except ProviderError as exc:
            return self._result(
                state,
                TurnStatus.FAILED,
                "provider_error",
                error=ErrorInfo(
                    kind=exc.kind.value,
                    message=str(exc),
                    retryable=exc.retryable,
                ),
            )
        except asyncio.CancelledError:
            return self._result(state, TurnStatus.CANCELLED, "cancelled")
        finally:
            await self.provider.aclose()

    async def _run_loop(self, state: _RunState) -> TurnResult:
        while state.model_calls < self.limits.max_model_calls:
            state.model_calls += 1
            request = ModelRequest(
                model=self.model,
                messages=tuple(state.messages),
                tools=self.tools.definitions,
            )
            text_parts: list[str] = []
            reasoning_parts: list[str] = []
            completed: ResponseCompleted | None = None

            async for event in self.provider.stream(request):
                if isinstance(event, TextDelta):
                    text_parts.append(event.text)
                    if self.on_text_delta is not None:
                        self.on_text_delta(event.text)
                elif isinstance(event, ReasoningDelta):
                    reasoning_parts.append(event.text)
                elif isinstance(event, ResponseCompleted):
                    completed = event

            if completed is None:
                return self._result(
                    state,
                    TurnStatus.FAILED,
                    "incomplete_provider_stream",
                    error=ErrorInfo(
                        kind="provider_protocol",
                        message="provider stream ended without ResponseCompleted",
                        retryable=False,
                    ),
                )

            state.usage = _add_usage(state.usage, completed.usage)
            response_text = "".join(text_parts)
            reasoning_content = "".join(reasoning_parts) or None
            if not completed.tool_calls:
                state.last_output_text = response_text
                return self._result(state, TurnStatus.COMPLETED, "completed")

            if state.tool_rounds >= self.limits.max_tool_rounds:
                state.last_output_text = response_text
                return self._result(state, TurnStatus.LIMITED, "tool_round_limit")

            state.tool_rounds += 1
            state.messages.append(
                ModelMessage(
                    role="assistant",
                    content=response_text or None,
                    tool_calls=completed.tool_calls,
                    reasoning_content=reasoning_content,
                )
            )
            for call in completed.tool_calls:
                if self.on_tool_activity is not None:
                    self.on_tool_activity(call.name, "started")
                result = await self.tools.execute(call, self.tool_context)
                state.tools_used.append(call.name)
                if self.on_tool_activity is not None:
                    status = "failed" if result.is_error else "completed"
                    self.on_tool_activity(call.name, status)
                state.messages.append(
                    ModelMessage(
                        role="tool",
                        content=result.content,
                        tool_call_id=result.tool_call_id,
                    )
                )

        return self._result(state, TurnStatus.LIMITED, "model_call_limit")

    @staticmethod
    def _result(
        state: _RunState,
        status: TurnStatus,
        stop_reason: str,
        *,
        error: ErrorInfo | None = None,
    ) -> TurnResult:
        return TurnResult(
            schema_version=1,
            session_id=state.session_id,
            turn_id=state.turn_id,
            status=status,
            stop_reason=stop_reason,
            output_text=state.last_output_text,
            verified=None,
            verification=(),
            tools_used=tuple(state.tools_used),
            usage=state.usage,
            error=error,
            model_calls=state.model_calls,
            tool_rounds=state.tool_rounds,
        )


def _add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    return TokenUsage(
        input_tokens=_add_optional(left.input_tokens, right.input_tokens),
        output_tokens=_add_optional(left.output_tokens, right.output_tokens),
        total_tokens=_add_optional(left.total_tokens, right.total_tokens),
    )


def _add_optional(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return None
    return (left or 0) + (right or 0)
