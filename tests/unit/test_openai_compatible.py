from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, AuthenticationError, BadRequestError, RateLimitError

from coding_agent.protocol import (
    ModelMessage,
    ModelRequest,
    ProviderError,
    ProviderErrorKind,
    ReasoningDelta,
    ResponseCompleted,
    TextDelta,
    ToolCall,
    ToolDefinition,
)
from coding_agent.providers.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
    classify_openai_error,
)


class AsyncChunkStream:
    def __init__(self, chunks: list[object]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> AsyncChunkStream:
        self._iterator = iter(self._chunks)
        return self

    async def __anext__(self) -> object:
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


def make_client(*chunks: object) -> SimpleNamespace:
    create = AsyncMock(return_value=AsyncChunkStream(list(chunks)))
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        close=AsyncMock(),
    )


def make_complete_client(response: object) -> SimpleNamespace:
    create = AsyncMock(return_value=response)
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        close=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_complete_converts_non_streaming_response_to_chat_response() -> None:
    choice = SimpleNamespace(
        message=SimpleNamespace(
            content="non-stream answer",
            reasoning_content=None,
            tool_calls=None,
        ),
        finish_reason="stop",
    )
    response = SimpleNamespace(
        choices=[choice],
        usage=SimpleNamespace(prompt_tokens=4, completion_tokens=2, total_tokens=6),
    )
    client = make_complete_client(response)
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(model="demo", api_key="test-key"), client=client
    )
    request = ModelRequest(model="demo", messages=(ModelMessage("user", "hi"),))

    result = await provider.complete(request)

    assert result.content == "non-stream answer"
    assert result.finish_reason == "stop"
    assert result.usage.total_tokens == 6
    call = client.chat.completions.create.await_args.kwargs
    assert call["stream"] is False
    assert call["model"] == "demo"
    assert "stream_options" not in call


@pytest.mark.asyncio
async def test_complete_parses_tool_calls_and_reasoning() -> None:
    tool_call = SimpleNamespace(
        id="call_9",
        function=SimpleNamespace(name="Read", arguments='{"path":"a"}'),
    )
    choice = SimpleNamespace(
        message=SimpleNamespace(
            content=None,
            reasoning_content="let me read",
            tool_calls=[tool_call],
        ),
        finish_reason="tool_calls",
    )
    response = SimpleNamespace(choices=[choice], usage=None)
    client = make_complete_client(response)
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(model="demo", api_key="test-key"), client=client
    )
    request = ModelRequest(
        model="demo",
        messages=(ModelMessage("user", "find it"),),
        tools=(ToolDefinition("Read", "read", {"type": "object"}),),
    )

    result = await provider.complete(request)

    assert result.content == ""
    assert result.reasoning_content == "let me read"
    assert result.tool_calls == (ToolCall("call_9", "Read", '{"path":"a"}'),)
    assert result.finish_reason == "tool_calls"
    assert result.usage.total_tokens is None
    assert client.chat.completions.create.await_args.kwargs["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_complete_classifies_provider_error_and_surfaces_compaction() -> None:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    error_response = httpx.Response(400, request=request)

    def raise_error(**kwargs: object) -> object:
        del kwargs
        raise BadRequestError(
            "prompt too long",
            response=error_response,
            body=None,
        )

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(side_effect=raise_error))
        ),
        close=AsyncMock(),
    )
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(model="demo", api_key="test-key"), client=client
    )

    with pytest.raises(ProviderError) as raised:
        await provider.complete(ModelRequest(model="demo", messages=(ModelMessage("user", "hi"),)))
    provider_error = raised.value
    assert provider_error.kind is ProviderErrorKind.PROMPT_TOO_LONG
    assert provider_error.requires_compaction is True


@pytest.mark.asyncio
async def test_stream_converts_sdk_chunks_to_internal_events() -> None:
    text_chunk = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"), finish_reason=None)],
        usage=None,
    )
    final_chunk = SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=None), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=4, completion_tokens=2, total_tokens=6),
    )
    client = make_client(text_chunk, final_chunk)
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(model="demo", api_key="test-key"),
        client=client,
    )
    request = ModelRequest(model="demo", messages=(ModelMessage("user", "hi"),))

    events = [event async for event in provider.stream(request)]

    assert events[0] == TextDelta("hello")
    assert isinstance(events[1], ResponseCompleted)
    assert events[1].finish_reason == "stop"
    assert events[1].usage.total_tokens == 6
    call = client.chat.completions.create.await_args.kwargs
    assert call["model"] == "demo"
    assert call["messages"] == [{"role": "user", "content": "hi"}]
    assert call["stream_options"] == {"include_usage": True}


@pytest.mark.asyncio
async def test_stream_usage_option_can_be_disabled() -> None:
    client = make_client(SimpleNamespace(choices=[], usage=None))
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            model="demo",
            api_key="test-key",
            include_stream_usage=False,
        ),
        client=client,
    )
    request = ModelRequest(model="demo", messages=(ModelMessage("user", "hi"),))

    _ = [event async for event in provider.stream(request)]

    call = client.chat.completions.create.await_args.kwargs
    assert "stream_options" not in call


@pytest.mark.asyncio
async def test_stream_accumulates_reasoning_and_tool_call_fragments() -> None:
    first = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=None,
                    reasoning_content="inspect ",
                    tool_calls=[
                        SimpleNamespace(
                            index=0,
                            id="call_1",
                            function=SimpleNamespace(name="Gr", arguments='{"query":"Pro'),
                        )
                    ],
                ),
                finish_reason=None,
            )
        ],
        usage=None,
    )
    second = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=None,
                    reasoning_content="source",
                    tool_calls=[
                        SimpleNamespace(
                            index=0,
                            id=None,
                            function=SimpleNamespace(name="ep", arguments='vider"}'),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=None,
    )
    client = make_client(first, second)
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(model="demo", api_key="test-key"), client=client
    )
    tool = ToolDefinition("Grep", "search", {"type": "object"})
    request = ModelRequest(
        model="demo",
        messages=(ModelMessage("user", "find it"),),
        tools=(tool,),
    )

    events = [event async for event in provider.stream(request)]

    assert events[:2] == [ReasoningDelta("inspect "), ReasoningDelta("source")]
    completed = events[-1]
    assert isinstance(completed, ResponseCompleted)
    assert completed.tool_calls == (ToolCall("call_1", "Grep", '{"query":"Provider"}'),)
    call = client.chat.completions.create.await_args.kwargs
    assert call["tool_choice"] == "auto"
    assert call["tools"][0]["function"]["name"] == "Grep"


@pytest.mark.asyncio
async def test_request_replays_assistant_reasoning_and_tool_result() -> None:
    client = make_client(SimpleNamespace(choices=[], usage=None))
    provider = OpenAICompatibleProvider(
        OpenAICompatibleConfig(model="demo", api_key="test-key"), client=client
    )
    request = ModelRequest(
        model="demo",
        messages=(
            ModelMessage(
                role="assistant",
                content=None,
                reasoning_content="I should inspect it.",
                tool_calls=(ToolCall("call_1", "Read", '{"path":"README.md"}'),),
            ),
            ModelMessage(role="tool", content="path: README.md", tool_call_id="call_1"),
        ),
    )

    _ = [event async for event in provider.stream(request)]

    messages = client.chat.completions.create.await_args.kwargs["messages"]
    assert messages[0]["reasoning_content"] == "I should inspect it."
    assert messages[0]["tool_calls"][0]["function"]["name"] == "Read"
    assert messages[1] == {
        "role": "tool",
        "content": "path: README.md",
        "tool_call_id": "call_1",
    }


def test_classifies_authentication_rate_limit_network_and_prompt_length() -> None:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")

    auth_response = httpx.Response(401, request=request)
    auth = classify_openai_error(AuthenticationError("bad key", response=auth_response, body=None))
    assert auth.kind is ProviderErrorKind.AUTHENTICATION
    assert auth.retryable is False

    rate_response = httpx.Response(429, request=request)
    rate = classify_openai_error(RateLimitError("slow down", response=rate_response, body=None))
    assert rate.kind is ProviderErrorKind.RATE_LIMIT
    assert rate.retryable is True

    network = classify_openai_error(APIConnectionError(request=request))
    assert network.kind is ProviderErrorKind.NETWORK
    assert network.retryable is True

    bad_response = httpx.Response(400, request=request)
    prompt = classify_openai_error(
        BadRequestError("context length exceeded", response=bad_response, body=None)
    )
    assert prompt.kind is ProviderErrorKind.PROMPT_TOO_LONG
    assert prompt.requires_compaction is True

    invalid = classify_openai_error(
        BadRequestError("bad field name", response=bad_response, body=None)
    )
    assert invalid.kind is ProviderErrorKind.INVALID_REQUEST
    assert invalid.requires_compaction is False
