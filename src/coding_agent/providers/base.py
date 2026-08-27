"""Provider seam：agent 主循环只依赖这里的抽象，不直接依赖厂商 SDK。

参照 FirstCoder FC:6 的 ``ChatProvider`` 形状，但按本项目简化——不引入完整的
``ProviderCapabilities`` 矩阵。``complete`` 与 ``stream`` 双形态共享同一套解析逻辑
（实现类把流式解析与完整解析收敛到同一内部函数），保证两条路径语义一致。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from coding_agent.protocol import ChatResponse, ModelRequest, ModelStreamEvent


class ChatProvider(Protocol):
    """非流式 ``complete`` 与流式 ``stream`` 双形态的 provider 协议。"""

    async def complete(self, request: ModelRequest) -> ChatResponse: ...

    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...

    async def aclose(self) -> None: ...
