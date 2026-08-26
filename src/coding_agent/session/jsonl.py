from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from coding_agent.protocol import ModelMessage, TokenUsage
from coding_agent.session.codec import (
    message_from,
    object_value,
    pending_from,
    pending_to_dict,
    usage_from,
)
from coding_agent.session.models import PendingPermission, SessionSnapshot, TurnIdentity
from coding_agent.session.store import SessionError, _add_optional

_SESSION_ID = re.compile(r"ses_[0-9a-f]{32}\Z")


class SessionEventKind(StrEnum):
    TURN_STARTED = "turn_started"
    MESSAGE_APPENDED = "message_appended"
    USAGE_ADDED = "usage_added"
    PERMISSION_PENDING = "permission_pending"
    PERMISSION_CLAIMED = "permission_claimed"


@dataclass(frozen=True, slots=True)
class SessionEvent:
    kind: SessionEventKind
    session_id: str
    payload: dict[str, object]
    schema_version: int = 1
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind.value,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "payload": self.payload,
        }


@dataclass(slots=True)
class _SessionView:
    session_id: str
    messages: list[ModelMessage] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    pending: dict[str, PendingPermission] = field(default_factory=dict)


class JsonlSessionStore:
    """Append-only durable Session backend with replay as its read path."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve(strict=False)
        self.root.mkdir(parents=True, exist_ok=True)

    def begin_turn(self, prompt: str, *, session_id: str | None = None) -> TurnIdentity:
        session_id = session_id or f"ses_{uuid4().hex}"
        path = self._path(session_id)
        if path.exists():
            view = self._replay(session_id)
            if view.pending:
                raise SessionError(
                    "pending_permission",
                    f"session has a pending permission: {session_id}",
                )
        identity = TurnIdentity(session_id=session_id, turn_id=f"turn_{uuid4().hex}")
        self._append(
            SessionEventKind.TURN_STARTED,
            session_id,
            {"turn_id": identity.turn_id, "prompt": prompt},
        )
        return identity

    def append_message(self, session_id: str, message: ModelMessage) -> None:
        self._require(session_id)
        self._append(
            SessionEventKind.MESSAGE_APPENDED,
            session_id,
            {"message": asdict(message)},
        )

    def add_usage(self, session_id: str, usage: TokenUsage) -> None:
        self._require(session_id)
        self._append(SessionEventKind.USAGE_ADDED, session_id, {"usage": usage.to_dict()})

    def snapshot(self, session_id: str) -> SessionSnapshot:
        view = self._replay(session_id)
        return SessionSnapshot(session_id, tuple(view.messages), view.usage)

    def save_pending(self, pending: PendingPermission) -> None:
        view = self._replay(pending.identity.session_id)
        if view.pending:
            raise SessionError(
                "pending_permission",
                f"session already has a pending permission: {pending.identity.session_id}",
            )
        self._append(
            SessionEventKind.PERMISSION_PENDING,
            pending.identity.session_id,
            {"pending": pending_to_dict(pending)},
        )

    def pending_for_session(self, session_id: str) -> PendingPermission | None:
        view = self._replay(session_id)
        return next(iter(view.pending.values()), None)

    def claim_pending(self, request_id: str, choice: str) -> PendingPermission:
        for path in sorted(self.root.glob("ses_*.jsonl")):
            view = self._replay(path.stem)
            pending = view.pending.get(request_id)
            if pending is None:
                continue
            self._append(
                SessionEventKind.PERMISSION_CLAIMED,
                pending.identity.session_id,
                {"request_id": request_id, "choice": choice},
            )
            return pending
        raise SessionError(
            "unknown_pending_permission",
            f"unknown pending permission request: {request_id}",
        )

    def list_sessions(self) -> tuple[dict[str, object], ...]:
        summaries: list[dict[str, object]] = []
        paths = sorted(
            self.root.glob("ses_*.jsonl"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for path in paths:
            view = self._replay(path.stem)
            pending = next(iter(view.pending.values()), None)
            summaries.append(
                {
                    "session_id": view.session_id,
                    "status": "waiting" if pending is not None else "ready",
                    "message_count": len(view.messages),
                    "total_tokens": view.usage.total_tokens,
                    "pending_request_id": (
                        None if pending is None else pending.request.request_id
                    ),
                    "updated_at": datetime.fromtimestamp(
                        path.stat().st_mtime, UTC
                    ).isoformat().replace("+00:00", "Z"),
                }
            )
        return tuple(summaries)

    def _append(
        self,
        kind: SessionEventKind,
        session_id: str,
        payload: dict[str, object],
    ) -> None:
        path = self._path(session_id)
        event = SessionEvent(kind, session_id, payload)
        try:
            line = json.dumps(
                event.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
        except (TypeError, ValueError) as exc:
            raise SessionError(
                "session_encoding",
                f"Session event is not JSON-safe: {exc}",
            ) from exc
        self._truncate_partial_tail(path)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _truncate_partial_tail(path: Path) -> None:
        if not path.exists():
            return
        with path.open("rb+") as handle:
            data = handle.read()
            if not data or data.endswith((b"\n", b"\r")):
                return
            last_newline = data.rfind(b"\n")
            handle.seek(0)
            handle.truncate(last_newline + 1)
            handle.flush()
            os.fsync(handle.fileno())

    def _replay(self, session_id: str) -> _SessionView:
        path = self._require(session_id)
        view = _SessionView(session_id)
        data = path.read_bytes()
        lines = data.splitlines(keepends=True)
        if lines and not lines[-1].endswith((b"\n", b"\r")):
            lines.pop()
        for line_number, raw_line in enumerate(lines, start=1):
            try:
                event = object_value(json.loads(raw_line.decode("utf-8")), "event")
                if event.get("schema_version") != 1:
                    raise ValueError("unsupported schema_version")
                if event.get("session_id") != session_id:
                    raise ValueError("session_id does not match filename")
                kind = SessionEventKind(str(event["kind"]))
                payload = object_value(event["payload"], "payload")
                self._reduce(view, kind, payload)
            except (KeyError, TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                raise SessionError(
                    "corrupt_session",
                    f"corrupt Session log {path} at line {line_number}: {exc}",
                ) from exc
        return view

    @staticmethod
    def _reduce(
        view: _SessionView,
        kind: SessionEventKind,
        payload: dict[str, object],
    ) -> None:
        if kind is SessionEventKind.TURN_STARTED:
            view.messages.append(ModelMessage("user", str(payload["prompt"])))
        elif kind is SessionEventKind.MESSAGE_APPENDED:
            view.messages.append(message_from(object_value(payload["message"], "message")))
        elif kind is SessionEventKind.USAGE_ADDED:
            usage = usage_from(object_value(payload["usage"], "usage"))
            view.usage = TokenUsage(
                _add_optional(view.usage.input_tokens, usage.input_tokens),
                _add_optional(view.usage.output_tokens, usage.output_tokens),
                _add_optional(view.usage.total_tokens, usage.total_tokens),
            )
        elif kind is SessionEventKind.PERMISSION_PENDING:
            pending = pending_from(object_value(payload["pending"], "pending"))
            view.pending[pending.request.request_id] = pending
        else:
            view.pending.pop(str(payload["request_id"]), None)

    def _require(self, session_id: str) -> Path:
        path = self._path(session_id)
        if not path.is_file():
            raise SessionError("unknown_session", f"unknown session: {session_id}")
        return path

    def _path(self, session_id: str) -> Path:
        if _SESSION_ID.fullmatch(session_id) is None:
            raise SessionError("invalid_session_id", f"invalid session id: {session_id}")
        return self.root / f"{session_id}.jsonl"
