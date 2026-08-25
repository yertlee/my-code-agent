from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from coding_agent.agent.limits import RuntimeLimits
from coding_agent.context import ContextBuilder
from coding_agent.permissions import PermissionPolicy, PermissionVerdict
from coding_agent.protocol import (
    ErrorInfo,
    ModelMessage,
    ProviderError,
    ReasoningDelta,
    ResponseCompleted,
    TextDelta,
    TokenUsage,
    ToolResult,
    TurnResult,
    TurnStatus,
)
from coding_agent.providers.base import ChatProvider
from coding_agent.runtime import (
    AgentCancelledError,
    CancellationToken,
    EventSink,
    NullEventSink,
    RuntimeEvent,
    RuntimeEventKind,
)
from coding_agent.session import SessionStore, TurnIdentity
from coding_agent.tools import ToolContext, ToolRegistry


@dataclass(slots=True)
class _TurnState:
    identity: TurnIdentity
    tools_used: list[str] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    model_calls: int = 0
    tool_rounds: int = 0
    last_output_text: str = ""


class AgentLoop:
    """The sole model-tool loop used by one-shot and interactive entry points."""

    def __init__(
        self,
        *,
        provider: ChatProvider,
        model: str,
        session_store: SessionStore,
        context_builder: ContextBuilder,
        permission_policy: PermissionPolicy,
        tool_context: ToolContext,
        tools: ToolRegistry,
        limits: RuntimeLimits | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.session_store = session_store
        self.context_builder = context_builder
        self.permission_policy = permission_policy
        self.tool_context = tool_context
        self.tools = tools
        self.limits = limits or RuntimeLimits()
        self.event_sink = event_sink or NullEventSink()

    async def run(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> TurnResult:
        identity = self.session_store.begin_turn(prompt, session_id=session_id)
        state = _TurnState(identity=identity)
        token = cancellation_token or CancellationToken()
        self._emit(state, RuntimeEventKind.TURN_STARTED, prompt=prompt)
        try:
            async with asyncio.timeout(self.limits.max_turn_seconds):
                return await self._run_loop(state, token)
        except TimeoutError:
            return self._finish(state, TurnStatus.LIMITED, "turn_timeout")
        except ProviderError as exc:
            return self._finish(
                state,
                TurnStatus.FAILED,
                "provider_error",
                error=ErrorInfo(
                    kind=exc.kind.value,
                    message=str(exc),
                    retryable=exc.retryable,
                ),
            )
        except (AgentCancelledError, asyncio.CancelledError):
            return self._finish(state, TurnStatus.CANCELLED, "cancelled")

    async def _run_loop(
        self,
        state: _TurnState,
        cancellation_token: CancellationToken,
    ) -> TurnResult:
        while state.model_calls < self.limits.max_model_calls:
            cancellation_token.raise_if_cancelled()
            state.model_calls += 1
            request = self.context_builder.build(
                model=self.model,
                snapshot=self.session_store.snapshot(state.identity.session_id),
                tools=self.tools.definitions,
            )
            text_parts: list[str] = []
            reasoning_parts: list[str] = []
            completed: ResponseCompleted | None = None

            async for event in self.provider.stream(request):
                cancellation_token.raise_if_cancelled()
                if isinstance(event, TextDelta):
                    text_parts.append(event.text)
                    self._emit(state, RuntimeEventKind.TEXT_DELTA, text=event.text)
                elif isinstance(event, ReasoningDelta):
                    reasoning_parts.append(event.text)
                elif isinstance(event, ResponseCompleted):
                    completed = event

            if completed is None:
                return self._finish(
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
            self.session_store.add_usage(state.identity.session_id, completed.usage)
            response_text = "".join(text_parts)
            reasoning_content = "".join(reasoning_parts) or None
            if not completed.tool_calls:
                state.last_output_text = response_text
                self.session_store.append_message(
                    state.identity.session_id,
                    ModelMessage(
                        role="assistant",
                        content=response_text or None,
                        reasoning_content=reasoning_content,
                    ),
                )
                return self._finish(state, TurnStatus.COMPLETED, "completed")

            if state.tool_rounds >= self.limits.max_tool_rounds:
                state.last_output_text = response_text
                return self._finish(state, TurnStatus.LIMITED, "tool_round_limit")

            state.tool_rounds += 1
            self.session_store.append_message(
                state.identity.session_id,
                ModelMessage(
                    role="assistant",
                    content=response_text or None,
                    tool_calls=completed.tool_calls,
                    reasoning_content=reasoning_content,
                ),
            )
            for call in completed.tool_calls:
                cancellation_token.raise_if_cancelled()
                self._emit(
                    state,
                    RuntimeEventKind.TOOL_STARTED,
                    tool_name=call.name,
                    tool_call_id=call.id,
                )
                decision = self.permission_policy.decide(call)
                if decision.verdict is PermissionVerdict.ALLOW:
                    result = await self.tools.execute(call, self.tool_context)
                else:
                    result = ToolResult(
                        tool_call_id=call.id,
                        tool_name=call.name,
                        content=f"ERROR [permission_denied]: {decision.reason}",
                        is_error=True,
                    )
                state.tools_used.append(call.name)
                self._emit(
                    state,
                    RuntimeEventKind.TOOL_COMPLETED,
                    tool_name=call.name,
                    tool_call_id=call.id,
                    is_error=result.is_error,
                    truncated=result.truncated,
                )
                self.session_store.append_message(
                    state.identity.session_id,
                    ModelMessage(
                        role="tool",
                        content=result.content,
                        tool_call_id=result.tool_call_id,
                    ),
                )

        return self._finish(state, TurnStatus.LIMITED, "model_call_limit")

    def _finish(
        self,
        state: _TurnState,
        status: TurnStatus,
        stop_reason: str,
        *,
        error: ErrorInfo | None = None,
    ) -> TurnResult:
        result = TurnResult(
            schema_version=1,
            session_id=state.identity.session_id,
            turn_id=state.identity.turn_id,
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
        self._emit(
            state,
            RuntimeEventKind.TURN_FINISHED,
            status=status.value,
            stop_reason=stop_reason,
        )
        return result

    def _emit(self, state: _TurnState, kind: RuntimeEventKind, **payload: object) -> None:
        self.event_sink.emit(
            RuntimeEvent(
                kind=kind,
                session_id=state.identity.session_id,
                turn_id=state.identity.turn_id,
                payload=payload,
            )
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
