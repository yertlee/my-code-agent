from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from openai import APIConnectionError, AuthenticationError, BadRequestError, RateLimitError

from coding_agent.protocol import (
    ModelMessage,
    ModelRequest,
    ProviderErrorKind,
    ResponseCompleted,
    TextDelta,
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


def test_classifies_authentication_rate_limit_network_and_prompt_length() -> None:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")

    auth_response = httpx.Response(401, request=request)
    auth = classify_openai_error(
        AuthenticationError("bad key", response=auth_response, body=None)
    )
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
