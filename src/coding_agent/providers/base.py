from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from coding_agent.protocol import ModelRequest, ModelStreamEvent


class ChatProvider(Protocol):
    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...

    async def aclose(self) -> None: ...
