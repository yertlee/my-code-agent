from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from coding_agent.protocol import (
    ErrorInfo,
    ModelMessage,
    ModelRequest,
    ProviderError,
    ResponseCompleted,
    TextDelta,
    TokenUsage,
    TurnResult,
    TurnStatus,
)
from coding_agent.providers.base import ChatProvider


async def run_prompt(
    provider: ChatProvider,
    *,
    prompt: str,
    model: str,
    on_text_delta: Callable[[str], None] | None = None,
) -> TurnResult:
    session_id = f"ses_{uuid4().hex}"
    turn_id = f"turn_{uuid4().hex}"
    request = ModelRequest(model=model, messages=(ModelMessage(role="user", content=prompt),))
    text_parts: list[str] = []
    usage = TokenUsage()

    try:
        async for event in provider.stream(request):
            if isinstance(event, TextDelta):
                text_parts.append(event.text)
                if on_text_delta is not None:
                    on_text_delta(event.text)
            elif isinstance(event, ResponseCompleted):
                usage = event.usage
    except ProviderError as exc:
        return TurnResult(
            schema_version=1,
            session_id=session_id,
            turn_id=turn_id,
            status=TurnStatus.FAILED,
            stop_reason="provider_error",
            output_text="".join(text_parts),
            verified=None,
            verification=(),
            tools_used=(),
            usage=usage,
            error=ErrorInfo(kind=exc.kind.value, message=str(exc), retryable=exc.retryable),
        )
    finally:
        await provider.aclose()

    return TurnResult(
        schema_version=1,
        session_id=session_id,
        turn_id=turn_id,
        status=TurnStatus.COMPLETED,
        stop_reason="completed",
        output_text="".join(text_parts),
        verified=None,
        verification=(),
        tools_used=(),
        usage=usage,
        error=None,
    )
