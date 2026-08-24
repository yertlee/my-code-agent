from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ProviderErrorKind(StrEnum):
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    NETWORK = "network"
    PROMPT_TOO_LONG = "prompt_too_long"
    INVALID_REQUEST = "invalid_request"
    SERVER_ERROR = "server_error"
    UNKNOWN = "unknown"


class TurnStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class ModelRequest:
    model: str
    messages: tuple[ModelMessage, ...]


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def to_dict(self) -> dict[str, int | None]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class ResponseCompleted:
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str | None = None


type ModelStreamEvent = TextDelta | ResponseCompleted


class ProviderError(Exception):
    def __init__(self, kind: ProviderErrorKind, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ErrorInfo:
    kind: str
    message: str
    retryable: bool

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "kind": self.kind,
            "message": self.message,
            "retryable": self.retryable,
        }


@dataclass(frozen=True, slots=True)
class TurnResult:
    schema_version: int
    session_id: str
    turn_id: str
    status: TurnStatus
    stop_reason: str
    output_text: str
    verified: bool | None
    verification: tuple[dict[str, object], ...]
    tools_used: tuple[str, ...]
    usage: TokenUsage
    error: ErrorInfo | None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "status": self.status.value,
            "stop_reason": self.stop_reason,
            "output_text": self.output_text,
            "verified": self.verified,
            "verification": list(self.verification),
            "tools_used": list(self.tools_used),
            "usage": self.usage.to_dict(),
            "error": None if self.error is None else self.error.to_dict(),
        }
