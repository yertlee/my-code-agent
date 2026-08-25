from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

from coding_agent.protocol import ModelMessage, TokenUsage
from coding_agent.session.models import SessionSnapshot, TurnIdentity


class SessionStore(Protocol):
    def begin_turn(self, prompt: str, *, session_id: str | None = None) -> TurnIdentity: ...

    def append_message(self, session_id: str, message: ModelMessage) -> None: ...

    def add_usage(self, session_id: str, usage: TokenUsage) -> None: ...

    def snapshot(self, session_id: str) -> SessionSnapshot: ...


@dataclass(slots=True)
class _SessionState:
    session_id: str
    messages: list[ModelMessage] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)


class InMemorySessionStore:
    """M3 session implementation; persistence is introduced in M5."""

    def __init__(self) -> None:
        self._sessions: dict[str, _SessionState] = {}

    def begin_turn(self, prompt: str, *, session_id: str | None = None) -> TurnIdentity:
        if session_id is None:
            session_id = f"ses_{uuid4().hex}"
            self._sessions[session_id] = _SessionState(session_id=session_id)
        state = self._require(session_id)
        state.messages.append(ModelMessage(role="user", content=prompt))
        return TurnIdentity(session_id=session_id, turn_id=f"turn_{uuid4().hex}")

    def append_message(self, session_id: str, message: ModelMessage) -> None:
        self._require(session_id).messages.append(message)

    def add_usage(self, session_id: str, usage: TokenUsage) -> None:
        state = self._require(session_id)
        state.usage = TokenUsage(
            input_tokens=_add_optional(state.usage.input_tokens, usage.input_tokens),
            output_tokens=_add_optional(state.usage.output_tokens, usage.output_tokens),
            total_tokens=_add_optional(state.usage.total_tokens, usage.total_tokens),
        )

    def snapshot(self, session_id: str) -> SessionSnapshot:
        state = self._require(session_id)
        return SessionSnapshot(
            session_id=state.session_id,
            messages=tuple(state.messages),
            usage=state.usage,
        )

    def _require(self, session_id: str) -> _SessionState:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise KeyError(f"unknown session: {session_id}") from exc


def _add_optional(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return None
    return (left or 0) + (right or 0)
