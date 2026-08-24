from __future__ import annotations

from collections.abc import AsyncIterator

from coding_agent.protocol import (
    ModelRequest,
    ModelStreamEvent,
    ProviderError,
    ResponseCompleted,
    TextDelta,
    TokenUsage,
)


class FakeProvider:
    def __init__(
        self,
        response_text: str = "这是 Fake Provider 的 M1 响应。",
        *,
        chunk_size: int = 4,
        usage: TokenUsage | None = None,
        error: ProviderError | None = None,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1")
        self.response_text = response_text
        self.chunk_size = chunk_size
        self.usage = usage or TokenUsage(input_tokens=8, output_tokens=10, total_tokens=18)
        self.error = error
        self.requests: list[ModelRequest] = []

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        self.requests.append(request)
        if self.error is not None:
            raise self.error

        for offset in range(0, len(self.response_text), self.chunk_size):
            yield TextDelta(self.response_text[offset : offset + self.chunk_size])
        yield ResponseCompleted(usage=self.usage, finish_reason="stop")

    async def aclose(self) -> None:
        return None
