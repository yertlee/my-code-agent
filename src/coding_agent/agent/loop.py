from __future__ import annotations

import asyncio

from coding_agent.agent.limits import RuntimeLimits
from coding_agent.agent.loop_helpers import (
    TurnState,
    add_usage,
    confirmation_fingerprint,
    confirmation_matches,
    latest_user_text,
    memory_summary,
    pending_input,
    state_from_pending,
)
from coding_agent.context import ContextBuilder
from coding_agent.memory.base import MemoryService
from coding_agent.memory.models import MemoryObservation, MemoryQuery, MemoryRecall
from coding_agent.permissions import (
    PermissionAction,
    PermissionManager,
    PermissionVerdict,
)
from coding_agent.protocol import (
    ChatResponse,
    ErrorInfo,
    ModelRequest,
    PendingInputInfo,
    ProviderError,
    ProviderErrorKind,
    ReasoningDelta,
    ResponseCompleted,
    TextDelta,
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
from coding_agent.session import (
    PendingPermission,
    SessionBackend,
    assistant_message,
    tool_result_message,
)
from coding_agent.tools.base import PreparedToolCall, ToolContext
from coding_agent.tools.registry import ToolRegistry


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
        stream_output: bool = False,
        memory_service: MemoryService | None = None,
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
        self.stream_output = stream_output
        self.memory_service = memory_service

    async def run(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> TurnResult:
        identity = self.session_store.begin_turn(prompt, session_id=session_id)
        state = TurnState(identity=identity)
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
        state = state_from_pending(pending)
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
            if isinstance(prepared, ToolResult) or not confirmation_matches(pending, prepared):
                result = ToolResult(
                    tool_call_id=pending.call.id,
                    tool_name=pending.call.name,
                    content="ERROR [stale_snapshot]: permission preview is no longer current",
                    is_error=True,
                )
                await self._record_tool_result(state, pending.call, result)
            else:
                result = await self._execute_prepared(state, prepared, token)
        else:
            result = self._permission_denied(pending.call, decision.reason)
            await self._record_tool_result(state, pending.call, result)
        continuation = await self._process_tool_calls(state, pending.remaining_calls, token)
        if continuation is not None:
            return continuation
        return await self._run_guarded(state, token)

    def pending_input(self, session_id: str) -> PendingInputInfo | None:
        pending = self.session_store.pending_for_session(session_id)
        return None if pending is None else pending_input(pending.request, pending.preview)

    async def _run_guarded(
        self,
        state: TurnState,
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
        state: TurnState,
        token: CancellationToken,
    ) -> TurnResult:
        memory = await self._recall_memory(state)
        while state.model_calls < self.limits.max_model_calls:
            token.raise_if_cancelled()
            state.model_calls += 1
            request = self.context_builder.build(
                model=self.model,
                snapshot=self.session_store.snapshot(state.identity.session_id),
                tools=self.tools.definitions,
                memory=memory,
            )
            self._emit_context_projection(state)
            projection = getattr(self.context_builder, "last_projection", None)
            if projection is not None and projection.budget_exceeded:
                return self._finish(
                    state,
                    TurnStatus.LIMITED,
                    "context_budget_exceeded",
                )
            response = (
                await self._complete_once(state, request, token)
                if self.stream_output
                else await self.provider.complete(request)
            )
            if response.error is not None:
                raise response.error
            if not self.stream_output and response.content:
                self._emit(state, RuntimeEventKind.TEXT_DELTA, text=response.content)
            continuation = await self._process_completion(state, response, token)
            if continuation is not None:
                return continuation
        return self._finish(state, TurnStatus.LIMITED, "model_call_limit")

    async def _complete_once(
        self,
        state: TurnState,
        request: ModelRequest,
        token: CancellationToken,
    ) -> ChatResponse:
        """可选的流式分支：逐事件累积成单个 ChatResponse，语义与 complete 一致。"""
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
            raise ProviderError(
                ProviderErrorKind.INVALID_REQUEST,
                "provider stream ended without ResponseCompleted",
                retryable=False,
            )
        return ChatResponse(
            content="".join(text_parts),
            reasoning_content="".join(reasoning_parts) or None,
            tool_calls=completed.tool_calls,
            finish_reason=completed.finish_reason,
            usage=completed.usage,
        )

    async def _process_completion(
        self,
        state: TurnState,
        response: ChatResponse,
        token: CancellationToken,
    ) -> TurnResult | None:
        """complete 与流式分支共用的响应结算逻辑。"""
        state.usage = add_usage(state.usage, response.usage)
        self.session_store.add_usage(state.identity.session_id, response.usage)
        if not response.tool_calls:
            state.last_output_text = response.content
            self.session_store.append_message(
                state.identity.session_id,
                assistant_message(
                    state.identity.session_id,
                    turn_id=state.identity.turn_id,
                    text=response.content or None,
                    reasoning_content=response.reasoning_content,
                ),
            )
            return self._finish(state, TurnStatus.COMPLETED, "completed")
        if state.tool_rounds >= self.limits.max_tool_rounds:
            state.last_output_text = response.content
            return self._finish(state, TurnStatus.LIMITED, "tool_round_limit")

        state.tool_rounds += 1
        self.session_store.append_message(
            state.identity.session_id,
            assistant_message(
                state.identity.session_id,
                turn_id=state.identity.turn_id,
                text=response.content or None,
                tool_calls=response.tool_calls,
                reasoning_content=response.reasoning_content,
            ),
        )
        continuation = await self._process_tool_calls(state, response.tool_calls, token)
        if continuation is not None:
            return continuation
        return None

    async def _process_tool_calls(
        self,
        state: TurnState,
        calls: tuple[ToolCall, ...],
        token: CancellationToken,
    ) -> TurnResult | None:
        for index, call in enumerate(calls):
            token.raise_if_cancelled()
            prepared = await self.tools.prepare(call, self.tool_context)
            if isinstance(prepared, ToolResult):
                await self._record_tool_result(state, call, prepared)
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
                await self._record_tool_result(state, call, result)
                continue
            await self._execute_prepared(state, prepared, token)
        return None

    async def _execute_prepared(
        self,
        state: TurnState,
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
        await self._record_tool_result(state, call, result)
        token.raise_if_cancelled()
        return result

    async def _record_tool_result(
        self,
        state: TurnState,
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
        message = tool_result_message(
            state.identity.session_id,
            result,
            turn_id=state.identity.turn_id,
        )
        self.session_store.append_message(state.identity.session_id, message)
        if self.memory_service is not None:
            written = await self.memory_service.observe(MemoryObservation((message,)))
            if written.records:
                state.memory_written_ids.extend(record.id for record in written.records)
                self._emit(
                    state,
                    RuntimeEventKind.MEMORY_WRITTEN,
                    count=len(written.records),
                    memory_ids=[record.id for record in written.records],
                )

    def _wait_for_permission(
        self,
        state: TurnState,
        prepared: PreparedToolCall,
        *,
        remaining_calls: tuple[ToolCall, ...],
    ) -> TurnResult:
        request = prepared.preflight.permission_request
        options = ["deny", "allow_once"]
        if request.action in {PermissionAction.WRITE, PermissionAction.DELETE}:
            options.append("allow_session")
        info = pending_input(request, prepared.preflight.preview, tuple(options))
        self.session_store.save_pending(
            PendingPermission(
                identity=state.identity,
                call=prepared.call,
                remaining_calls=remaining_calls,
                request=request,
                preview=prepared.preflight.preview,
                confirmation_fingerprint=confirmation_fingerprint(
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
            question=info.question,
            options=list(info.options),
        )
        return self._finish(
            state,
            TurnStatus.WAITING,
            "waiting_for_permission",
            pending_input=info,
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
        state: TurnState,
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
            context=self._context_summary(),
            memory=memory_summary(state, enabled=self.memory_service is not None),
        )
        self._emit(
            state,
            RuntimeEventKind.TURN_FINISHED,
            status=status.value,
            stop_reason=stop_reason,
        )
        return result

    def _emit(self, state: TurnState, kind: RuntimeEventKind, **payload: object) -> None:
        self.event_sink.emit(
            RuntimeEvent(kind, state.identity.session_id, state.identity.turn_id, payload)
        )

    def _emit_context_projection(self, state: TurnState) -> None:
        """暴露预算化投影元数据（Stage 4 压缩触发与 Stage 5 可观测性原料）。

        仅当 builder 是 ``BudgetedContextBuilder`` 时才有 projection；无预算基线不发送。
        """
        projection = getattr(self.context_builder, "last_projection", None)
        if projection is not None:
            self._emit(
                state,
                RuntimeEventKind.CONTEXT_PROJECTED,
                **projection.to_event_payload(),
            )

    def _context_summary(self) -> dict[str, object] | None:
        projection = getattr(self.context_builder, "last_projection", None)
        return None if projection is None else projection.to_event_payload()

    async def _recall_memory(self, state: TurnState) -> MemoryRecall | None:
        if self.memory_service is None:
            return None
        snapshot = self.session_store.snapshot(state.identity.session_id)
        task = latest_user_text(snapshot, state.identity.turn_id)
        recall = await self.memory_service.recall(MemoryQuery(task=task))
        state.memory_considered = recall.considered
        state.memory_recalled_ids = [hit.record.id for hit in recall.hits]
        self._emit(
            state,
            RuntimeEventKind.MEMORY_RECALLED,
            considered=recall.considered,
            recalled=len(recall.hits),
            memory_ids=[hit.record.id for hit in recall.hits],
        )
        return recall
