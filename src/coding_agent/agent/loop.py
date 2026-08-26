from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from hashlib import sha256

from coding_agent.agent.limits import RuntimeLimits
from coding_agent.context import ContextBuilder
from coding_agent.permissions import (
    PermissionAction,
    PermissionManager,
    PermissionRequest,
    PermissionVerdict,
)
from coding_agent.protocol import (
    ErrorInfo,
    ModelMessage,
    PendingInputInfo,
    ProviderError,
    ReasoningDelta,
    ResponseCompleted,
    TextDelta,
    TokenUsage,
    ToolCall,
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
from coding_agent.session import PendingPermission, SessionBackend, TurnIdentity
from coding_agent.tools.base import PreparedToolCall, ToolContext
from coding_agent.tools.registry import ToolRegistry


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
        session_store: SessionBackend,
        context_builder: ContextBuilder,
        permission_manager: PermissionManager,
        tool_context: ToolContext,
        tools: ToolRegistry,
        limits: RuntimeLimits | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.session_store = session_store
        self.context_builder = context_builder
        self.permission_manager = permission_manager
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
        return await self._run_guarded(state, token)

    async def resume_permission(
        self,
        request_id: str,
        choice: str,
        *,
        cancellation_token: CancellationToken | None = None,
    ) -> TurnResult:
        pending = self.session_store.claim_pending(request_id, choice)
        state = _state_from_pending(pending)
        token = cancellation_token or CancellationToken()
        decision = self.permission_manager.resolve(pending.request, choice)
        self._emit(
            state,
            RuntimeEventKind.PERMISSION_RESOLVED,
            request_id=request_id,
            verdict=decision.verdict.value,
            choice=choice,
        )
        if decision.verdict is PermissionVerdict.ALLOW:
            prepared = await self.tools.prepare(pending.call, self.tool_context)
            if isinstance(prepared, ToolResult) or not _confirmation_matches(pending, prepared):
                result = ToolResult(
                    tool_call_id=pending.call.id,
                    tool_name=pending.call.name,
                    content="ERROR [stale_snapshot]: permission preview is no longer current",
                    is_error=True,
                )
                self._record_tool_result(state, pending.call, result)
            else:
                result = await self._execute_prepared(state, prepared, token)
        else:
            result = self._permission_denied(pending.call, decision.reason)
            self._record_tool_result(state, pending.call, result)
        continuation = await self._process_tool_calls(state, pending.remaining_calls, token)
        if continuation is not None:
            return continuation
        return await self._run_guarded(state, token)

    def pending_input(self, session_id: str) -> PendingInputInfo | None:
        pending = self.session_store.pending_for_session(session_id)
        return None if pending is None else _pending_input(pending.request, pending.preview)

    async def _run_guarded(
        self,
        state: _TurnState,
        token: CancellationToken,
    ) -> TurnResult:
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
                error=ErrorInfo(exc.kind.value, str(exc), exc.retryable),
            )
        except (AgentCancelledError, asyncio.CancelledError):
            return self._finish(state, TurnStatus.CANCELLED, "cancelled")

    async def _run_loop(
        self,
        state: _TurnState,
        token: CancellationToken,
    ) -> TurnResult:
        while state.model_calls < self.limits.max_model_calls:
            token.raise_if_cancelled()
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
                token.raise_if_cancelled()
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
                        "provider_protocol",
                        "provider stream ended without ResponseCompleted",
                        False,
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
                        "assistant",
                        response_text or None,
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
            continuation = await self._process_tool_calls(state, completed.tool_calls, token)
            if continuation is not None:
                return continuation
        return self._finish(state, TurnStatus.LIMITED, "model_call_limit")

    async def _process_tool_calls(
        self,
        state: _TurnState,
        calls: tuple[ToolCall, ...],
        token: CancellationToken,
    ) -> TurnResult | None:
        for index, call in enumerate(calls):
            token.raise_if_cancelled()
            prepared = await self.tools.prepare(call, self.tool_context)
            if isinstance(prepared, ToolResult):
                self._record_tool_result(state, call, prepared)
                continue
            if prepared.preflight.preview is not None:
                self._emit(
                    state,
                    RuntimeEventKind.DIFF_READY,
                    tool_name=call.name,
                    preview=prepared.preflight.preview,
                )
            decision = self.permission_manager.preflight(prepared.preflight.permission_request)
            if decision.verdict is PermissionVerdict.ASK:
                return self._wait_for_permission(
                    state,
                    prepared,
                    remaining_calls=calls[index + 1 :],
                )
            if decision.verdict is PermissionVerdict.DENY:
                result = self._permission_denied(call, decision.reason)
                self._record_tool_result(state, call, result)
                continue
            await self._execute_prepared(state, prepared, token)
        return None

    async def _execute_prepared(
        self,
        state: _TurnState,
        prepared: PreparedToolCall,
        token: CancellationToken,
    ) -> ToolResult:
        token.raise_if_cancelled()
        call = prepared.call
        self._emit(
            state,
            RuntimeEventKind.TOOL_STARTED,
            tool_name=call.name,
            tool_call_id=call.id,
        )
        result = await self.tools.execute_prepared(prepared, self.tool_context)
        self._record_tool_result(state, call, result)
        token.raise_if_cancelled()
        return result

    def _record_tool_result(
        self,
        state: _TurnState,
        call: ToolCall,
        result: ToolResult,
    ) -> None:
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
            ModelMessage("tool", result.content, tool_call_id=result.tool_call_id),
        )

    def _wait_for_permission(
        self,
        state: _TurnState,
        prepared: PreparedToolCall,
        *,
        remaining_calls: tuple[ToolCall, ...],
    ) -> TurnResult:
        request = prepared.preflight.permission_request
        options = ["deny", "allow_once"]
        if request.action in {PermissionAction.WRITE, PermissionAction.DELETE}:
            options.append("allow_session")
        pending_input = _pending_input(request, prepared.preflight.preview, tuple(options))
        self.session_store.save_pending(
            PendingPermission(
                identity=state.identity,
                call=prepared.call,
                remaining_calls=remaining_calls,
                request=request,
                preview=prepared.preflight.preview,
                confirmation_fingerprint=_confirmation_fingerprint(
                    request,
                    prepared.preflight.preview,
                ),
                tools_used=tuple(state.tools_used),
                usage=state.usage,
                model_calls=state.model_calls,
                tool_rounds=state.tool_rounds,
                last_output_text=state.last_output_text,
            )
        )
        self._emit(
            state,
            RuntimeEventKind.PERMISSION_REQUESTED,
            request_id=request.request_id,
            question=pending_input.question,
            options=list(pending_input.options),
        )
        return self._finish(
            state,
            TurnStatus.WAITING,
            "waiting_for_permission",
            pending_input=pending_input,
        )

    @staticmethod
    def _permission_denied(call: ToolCall, reason: str) -> ToolResult:
        return ToolResult(
            tool_call_id=call.id,
            tool_name=call.name,
            content=f"ERROR [permission_denied]: {reason}",
            is_error=True,
        )

    def _finish(
        self,
        state: _TurnState,
        status: TurnStatus,
        stop_reason: str,
        *,
        error: ErrorInfo | None = None,
        pending_input: PendingInputInfo | None = None,
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
            pending_input=pending_input,
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
            RuntimeEvent(kind, state.identity.session_id, state.identity.turn_id, payload)
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


def _state_from_pending(pending: PendingPermission) -> _TurnState:
    return _TurnState(
        identity=pending.identity,
        tools_used=list(pending.tools_used),
        usage=pending.usage,
        model_calls=pending.model_calls,
        tool_rounds=pending.tool_rounds,
        last_output_text=pending.last_output_text,
    )


def _pending_input(
    request: PermissionRequest,
    preview: dict[str, object] | None,
    options: tuple[str, ...] | None = None,
) -> PendingInputInfo:
    display_target = str(request.metadata.get("path") or request.target)
    if options is None:
        values = ["deny", "allow_once"]
        if request.action in {PermissionAction.WRITE, PermissionAction.DELETE}:
            values.append("allow_session")
        options = tuple(values)
    return PendingInputInfo(
        request_id=request.request_id,
        kind="permission_confirmation",
        question=f"Allow {request.action.value}: {display_target}?",
        options=options,
        payload={
            "action": request.action.value,
            "target": display_target,
            "reason": request.reason,
            "preview": preview,
        },
    )


def _confirmation_matches(
    pending: PendingPermission,
    prepared: PreparedToolCall,
) -> bool:
    return pending.confirmation_fingerprint == _confirmation_fingerprint(
        prepared.preflight.permission_request,
        prepared.preflight.preview,
    )


def _confirmation_fingerprint(
    request: PermissionRequest,
    preview: dict[str, object] | None,
) -> str:
    payload = {
        "action": request.action.value,
        "target": request.target,
        "reason": request.reason,
        "metadata": request.metadata,
        "preview": preview,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
