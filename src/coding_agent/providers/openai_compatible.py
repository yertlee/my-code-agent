from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    OpenAIError,
    RateLimitError,
)

from coding_agent.protocol import (
    ModelRequest,
    ModelStreamEvent,
    ProviderError,
    ProviderErrorKind,
    ResponseCompleted,
    TextDelta,
    TokenUsage,
)


@dataclass(frozen=True, slots=True)
class OpenAICompatibleConfig:
    model: str
    api_key: str
    base_url: str | None = None
    timeout_seconds: float = 60.0
    include_stream_usage: bool = True


class OpenAICompatibleProvider:
    def __init__(self, config: OpenAICompatibleConfig, *, client: Any | None = None) -> None:
        self.config = config
        self._owns_client = client is None
        self._client = client or AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        messages = [
            {"role": message.role, "content": message.content} for message in request.messages
        ]
        create: Any = self._client.chat.completions.create
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "stream": True,
        }
        if self.config.include_stream_usage:
            kwargs["stream_options"] = {"include_usage": True}

        usage = TokenUsage()
        finish_reason: str | None = None
        try:
            stream: Any = await create(**kwargs)
            async for chunk in stream:
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    usage = TokenUsage(
                        input_tokens=getattr(chunk_usage, "prompt_tokens", None),
                        output_tokens=getattr(chunk_usage, "completion_tokens", None),
                        total_tokens=getattr(chunk_usage, "total_tokens", None),
                    )

                for choice in getattr(chunk, "choices", ()):
                    reason = getattr(choice, "finish_reason", None)
                    if reason is not None:
                        finish_reason = str(reason)
                    delta = getattr(choice, "delta", None)
                    content = getattr(delta, "content", None)
                    if isinstance(content, str) and content:
                        yield TextDelta(content)
        except OpenAIError as exc:
            raise classify_openai_error(exc) from exc

        yield ResponseCompleted(usage=usage, finish_reason=finish_reason)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.close()


def classify_openai_error(exc: OpenAIError) -> ProviderError:
    message = _safe_message(exc)
    if isinstance(exc, AuthenticationError):
        return ProviderError(ProviderErrorKind.AUTHENTICATION, message, retryable=False)
    if isinstance(exc, RateLimitError):
        return ProviderError(ProviderErrorKind.RATE_LIMIT, message, retryable=True)
    if isinstance(exc, APITimeoutError):
        return ProviderError(ProviderErrorKind.TIMEOUT, message, retryable=True)
    if isinstance(exc, APIConnectionError):
        return ProviderError(ProviderErrorKind.NETWORK, message, retryable=True)
    if isinstance(exc, BadRequestError):
        lowered = message.casefold()
        prompt_markers = ("context length", "context window", "too many tokens", "prompt too long")
        kind = (
            ProviderErrorKind.PROMPT_TOO_LONG
            if any(marker in lowered for marker in prompt_markers)
            else ProviderErrorKind.INVALID_REQUEST
        )
        return ProviderError(kind, message, retryable=False)
    if isinstance(exc, APIStatusError) and exc.status_code >= 500:
        return ProviderError(ProviderErrorKind.SERVER_ERROR, message, retryable=True)
    return ProviderError(ProviderErrorKind.UNKNOWN, message, retryable=False)


def _safe_message(exc: OpenAIError) -> str:
    text = str(exc).strip()
    return text if text else exc.__class__.__name__
