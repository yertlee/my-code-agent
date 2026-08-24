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
    ModelMessage,
    ModelRequest,
    ModelStreamEvent,
    ProviderError,
    ProviderErrorKind,
    ReasoningDelta,
    ResponseCompleted,
    TextDelta,
    TokenUsage,
    ToolCall,
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
        create: Any = self._client.chat.completions.create
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": [_message_to_payload(message) for message in request.messages],
            "stream": True,
        }
        if request.tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in request.tools
            ]
            kwargs["tool_choice"] = "auto"
        if self.config.include_stream_usage:
            kwargs["stream_options"] = {"include_usage": True}

        usage = TokenUsage()
        finish_reason: str | None = None
        tool_call_parts: dict[int, dict[str, str]] = {}
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
                    reasoning_content = getattr(delta, "reasoning_content", None)
                    if isinstance(reasoning_content, str) and reasoning_content:
                        yield ReasoningDelta(reasoning_content)
                    for call_delta in getattr(delta, "tool_calls", ()) or ():
                        index = int(getattr(call_delta, "index", 0))
                        parts = tool_call_parts.setdefault(
                            index, {"id": "", "name": "", "arguments": ""}
                        )
                        call_id = getattr(call_delta, "id", None)
                        if isinstance(call_id, str) and call_id:
                            parts["id"] = call_id
                        function = getattr(call_delta, "function", None)
                        name = getattr(function, "name", None)
                        if isinstance(name, str) and name:
                            parts["name"] += name
                        arguments = getattr(function, "arguments", None)
                        if isinstance(arguments, str) and arguments:
                            parts["arguments"] += arguments
        except OpenAIError as exc:
            raise classify_openai_error(exc) from exc

        tool_calls = _build_tool_calls(tool_call_parts)
        yield ResponseCompleted(
            usage=usage,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
        )

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


def _message_to_payload(message: ModelMessage) -> dict[str, object]:
    payload: dict[str, object] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments_json},
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    if message.reasoning_content is not None:
        # DeepSeek thinking-mode tool turns must replay this field verbatim.
        payload["reasoning_content"] = message.reasoning_content
    return payload


def _build_tool_calls(parts_by_index: dict[int, dict[str, str]]) -> tuple[ToolCall, ...]:
    calls: list[ToolCall] = []
    for index in sorted(parts_by_index):
        parts = parts_by_index[index]
        if not parts["id"] or not parts["name"]:
            raise ProviderError(
                ProviderErrorKind.INVALID_REQUEST,
                f"provider returned incomplete tool call at index {index}",
                retryable=False,
            )
        calls.append(
            ToolCall(
                id=parts["id"],
                name=parts["name"],
                arguments_json=parts["arguments"] or "{}",
            )
        )
    return tuple(calls)
