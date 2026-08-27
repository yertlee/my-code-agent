from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import uuid4

from coding_agent.protocol import TokenUsage
from coding_agent.session.facts import AgentMessage, user_message
from coding_agent.session.models import PendingPermission, SessionSnapshot, TurnIdentity


class SessionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class SessionStore(Protocol):
    """Session 事实层协议：以 AgentMessage 事实账本为唯一存储格式。

    ``begin_turn`` 会把用户 prompt 落成一条 role=user 的事实消息；``append_message``
    接收已构造的 AgentMessage 事实（assistant/tool 等），从不接收 provider 侧的
    ModelMessage —— 事实与 provider 请求格式严格分离。
    """

    def begin_turn(self, prompt: str, *, session_id: str | None = None) -> TurnIdentity: ...

    def append_message(self, session_id: str, message: AgentMessage) -> None: ...

    def add_usage(self, session_id: str, usage: TokenUsage) -> None: ...

    def snapshot(self, session_id: str) -> SessionSnapshot: ...


class PendingPermissionStore(Protocol):
    def save_pending(self, pending: PendingPermission) -> None: ...

    def pending_for_session(self, session_id: str) -> PendingPermission | None: ...

    def claim_pending(self, request_id: str, choice: str) -> PendingPermission: ...


class SessionBackend(SessionStore, PendingPermissionStore, Protocol):
    pass


@dataclass(slots=True)
class _SessionState:
    session_id: str
    messages: list[AgentMessage] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)


class InMemorySessionStore:
    """In-process Session backend used by the default lightweight preset."""

    def __init__(self) -> None:
        self._sessions: dict[str, _SessionState] = {}
        self._pending: dict[str, PendingPermission] = {}

    def begin_turn(self, prompt: str, *, session_id: str | None = None) -> TurnIdentity:
        if session_id is None:
            session_id = f"ses_{uuid4().hex}"
            self._sessions[session_id] = _SessionState(session_id=session_id)
        state = self._require(session_id)
        identity = TurnIdentity(session_id=session_id, turn_id=f"turn_{uuid4().hex}")
        state.messages.append(user_message(session_id, prompt, turn_id=identity.turn_id))
        return identity

    def append_message(self, session_id: str, message: AgentMessage) -> None:
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

    def save_pending(self, pending: PendingPermission) -> None:
        existing = self.pending_for_session(pending.identity.session_id)
        if existing is not None:
            raise SessionError(
                "pending_permission",
                f"session already has a pending permission: {pending.identity.session_id}",
            )
        self._pending[pending.request.request_id] = pending

    def pending_for_session(self, session_id: str) -> PendingPermission | None:
        self._require(session_id)
        return next(
            (
                pending
                for pending in self._pending.values()
                if pending.identity.session_id == session_id
            ),
            None,
        )

    def claim_pending(self, request_id: str, choice: str) -> PendingPermission:
        del choice
        try:
            return self._pending.pop(request_id)
        except KeyError as exc:
            raise SessionError(
                "unknown_pending_permission",
                f"unknown pending permission request: {request_id}",
            ) from exc


def _add_optional(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return None
    return (left or 0) + (right or 0)
