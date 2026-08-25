from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field

from coding_agent.protocol import (
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
class FakeResponse:
    text: str = ""
    reasoning_content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: TokenUsage = field(
        default_factory=lambda: TokenUsage(input_tokens=8, output_tokens=10, total_tokens=18)
    )
    error: ProviderError | None = None
    finish_reason: str | None = None


class FakeProvider:
    def __init__(
        self,
        response_text: str = "这是 Fake Provider 的 M1 响应。",
        *,
        script: Sequence[FakeResponse] | None = None,
        chunk_size: int = 4,
        usage: TokenUsage | None = None,
        error: ProviderError | None = None,
        repeat: bool = False,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1")
        default_usage = usage or TokenUsage(input_tokens=8, output_tokens=10, total_tokens=18)
        self.script = (
            tuple(script)
            if script is not None
            else (FakeResponse(text=response_text, usage=default_usage, error=error),)
        )
        if not self.script:
            raise ValueError("script must contain at least one response")
        self.chunk_size = chunk_size
        self.repeat = repeat
        self.requests: list[ModelRequest] = []
        self.close_calls = 0

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        response_index = len(self.requests)
        self.requests.append(request)
        if response_index >= len(self.script):
            if self.repeat:
                response_index %= len(self.script)
            else:
                raise ProviderError(
                    ProviderErrorKind.UNKNOWN,
                    "FakeProvider script exhausted",
                    retryable=False,
                )
        response = self.script[response_index]
        if response.error is not None:
            raise response.error

        for offset in range(0, len(response.reasoning_content), self.chunk_size):
            yield ReasoningDelta(response.reasoning_content[offset : offset + self.chunk_size])
        for offset in range(0, len(response.text), self.chunk_size):
            yield TextDelta(response.text[offset : offset + self.chunk_size])
        finish_reason = response.finish_reason
        if finish_reason is None:
            finish_reason = "tool_calls" if response.tool_calls else "stop"
        yield ResponseCompleted(
            usage=response.usage,
            finish_reason=finish_reason,
            tool_calls=response.tool_calls,
        )

    async def aclose(self) -> None:
        self.close_calls += 1


def readonly_demo_script(final_text: str) -> tuple[FakeResponse, ...]:
    return (
        FakeResponse(
            reasoning_content="I need to locate the symbol.",
            tool_calls=(
                ToolCall(
                    id="call_grep",
                    name="Grep",
                    arguments_json=(
                        '{"query":"class ProviderErrorKind","glob":"**/*.py",'
                        '"path":"src","max_results":20}'
                    ),
                ),
            ),
        ),
        FakeResponse(
            reasoning_content="The search result identifies the source file.",
            tool_calls=(
                ToolCall(
                    id="call_read",
                    name="Read",
                    arguments_json=(
                        '{"path":"src/coding_agent/protocol/models.py",'
                        '"start_line":1,"end_line":35}'
                    ),
                ),
            ),
        ),
        FakeResponse(text=final_text),
    )
