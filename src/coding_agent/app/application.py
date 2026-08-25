from __future__ import annotations

from dataclasses import dataclass, field

from coding_agent.agent import AgentLoop
from coding_agent.protocol import TurnResult
from coding_agent.providers.base import ChatProvider
from coding_agent.runtime import CancellationToken


@dataclass(slots=True)
class AgentApplication:
    """Lifecycle boundary shared by one-shot and interactive CLI modes."""

    agent_loop: AgentLoop
    provider: ChatProvider
    active_session_id: str | None = None
    _active_token: CancellationToken | None = field(default=None, init=False)
    _closed: bool = field(default=False, init=False)

    async def run(self, prompt: str) -> TurnResult:
        if self._closed:
            raise RuntimeError("application is closed")
        if self._active_token is not None:
            raise RuntimeError("another turn is already running")
        token = CancellationToken()
        self._active_token = token
        try:
            result = await self.agent_loop.run(
                prompt,
                session_id=self.active_session_id,
                cancellation_token=token,
            )
            self.active_session_id = result.session_id
            return result
        finally:
            self._active_token = None

    async def resume_permission(self, request_id: str, choice: str) -> TurnResult:
        if self._closed:
            raise RuntimeError("application is closed")
        if self._active_token is not None:
            raise RuntimeError("another turn is already running")
        token = CancellationToken()
        self._active_token = token
        try:
            return await self.agent_loop.resume_permission(
                request_id,
                choice,
                cancellation_token=token,
            )
        finally:
            self._active_token = None

    def cancel_current_turn(self) -> None:
        if self._active_token is not None:
            self._active_token.cancel()

    async def aclose(self) -> None:
        if self._closed:
            return
        self.cancel_current_turn()
        await self.provider.aclose()
        self._closed = True

    async def __aenter__(self) -> AgentApplication:
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc_type, exc, traceback
        await self.aclose()
