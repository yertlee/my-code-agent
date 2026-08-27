from __future__ import annotations

import pytest

from coding_agent.app import build_application
from coding_agent.protocol import (
    ModelMessage,
    ModelRequest,
    ProviderError,
    ProviderErrorKind,
    ReasoningDelta,
    ResponseCompleted,
    TextDelta,
    TokenUsage,
    ToolCall,
    TurnStatus,
)
from coding_agent.providers.fake import FakeProvider, FakeResponse
from coding_agent.runtime import RecordingEventSink, RuntimeEventKind
from coding_agent.tools import ToolRegistry
from coding_agent.workspace import Workspace


@pytest.mark.asyncio
async def test_application_completes_and_records_request(tmp_path) -> None:
    provider = FakeProvider("abcdef", chunk_size=2)
    events = RecordingEventSink()
    application = build_application(
        provider=provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(),
        event_sink=events,
    )
    result = await application.run("hello")
    await application.aclose()

    # loop 主路径走 complete：文本整体 emit 一次（不按 chunk_size 切分）。
    seen = [
        str(event.payload["text"])
        for event in events.events
        if event.kind is RuntimeEventKind.TEXT_DELTA
    ]

    assert seen == ["abcdef"]
    assert result.status is TurnStatus.COMPLETED
    assert result.output_text == "abcdef"
    assert result.usage.total_tokens == 18
    assert provider.requests[0].messages[-1].content == "hello"


@pytest.mark.asyncio
async def test_fake_provider_complete_returns_aggregated_response() -> None:
    tool = ToolCall("call_1", "Grep", '{"query":"Target"}')
    provider = FakeProvider(
        script=(
            FakeResponse(
                text="final text",
                reasoning_content="reasoning",
                tool_calls=(tool,),
                usage=TokenUsage(input_tokens=2, output_tokens=3, total_tokens=5),
                finish_reason="tool_calls",
            ),
        )
    )
    request = ModelRequest(model="fake-model", messages=(ModelMessage("user", "hi"),))

    response = await provider.complete(request)

    assert response.content == "final text"
    assert response.reasoning_content == "reasoning"
    assert response.tool_calls == (tool,)
    assert response.finish_reason == "tool_calls"
    assert response.usage.total_tokens == 5
    assert response.error is None
    assert provider.requests == [request]


@pytest.mark.asyncio
async def test_fake_provider_complete_infers_finish_reason_and_carries_error() -> None:
    plain = FakeProvider(response_text="plain")
    plain_response = await plain.complete(
        ModelRequest(model="m", messages=(ModelMessage("user", "hi"),))
    )
    assert plain_response.finish_reason == "stop"

    provider_error = ProviderError(ProviderErrorKind.RATE_LIMIT, "slow down", retryable=True)
    failing = FakeProvider(error=provider_error)
    error_response = await failing.complete(
        ModelRequest(model="m", messages=(ModelMessage("user", "hi"),))
    )
    assert error_response.error is provider_error


@pytest.mark.asyncio
async def test_fake_provider_stream_chunks_text_and_tool_calls() -> None:
    provider = FakeProvider(
        script=(
            FakeResponse(
                reasoning_content="think",
                text="answer",
                tool_calls=(ToolCall("call_1", "Read", '{"path":"a"}'),),
            ),
        ),
        chunk_size=2,
    )
    request = ModelRequest(model="fake-model", messages=(ModelMessage("user", "hi"),))

    events = [event async for event in provider.stream(request)]

    assert events[0] == ReasoningDelta("th")
    assert events[1] == ReasoningDelta("in")
    assert events[2] == ReasoningDelta("k")
    assert events[3] == TextDelta("an")
    assert events[4] == TextDelta("sw")
    assert events[5] == TextDelta("er")
    completed = events[-1]
    assert isinstance(completed, ResponseCompleted)
    assert completed.finish_reason == "tool_calls"
    assert completed.tool_calls == (ToolCall("call_1", "Read", '{"path":"a"}'),)


@pytest.mark.asyncio
async def test_provider_error_becomes_failed_turn_result(tmp_path) -> None:
    provider = FakeProvider(
        error=ProviderError(ProviderErrorKind.RATE_LIMIT, "slow down", retryable=True)
    )

    application = build_application(
        provider=provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(),
    )
    result = await application.run("hello")
    await application.aclose()

    assert result.status is TurnStatus.FAILED
    assert result.stop_reason == "provider_error"
    assert result.error is not None
    assert result.error.kind == "rate_limit"
    assert result.error.retryable is True


def test_fake_provider_rejects_invalid_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        FakeProvider(chunk_size=0)
