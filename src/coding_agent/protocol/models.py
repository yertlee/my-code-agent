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
    WAITING = "waiting"
    LIMITED = "limited"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments_json: str


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool_call_id: str
    tool_name: str
    content: str
    is_error: bool = False
    truncated: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelMessage:
    role: str
    content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    reasoning_content: str | None = None


@dataclass(frozen=True, slots=True)
class ModelRequest:
    model: str
    messages: tuple[ModelMessage, ...]
    tools: tuple[ToolDefinition, ...] = ()


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
class ReasoningDelta:
    text: str


@dataclass(frozen=True, slots=True)
class ResponseCompleted:
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


type ModelStreamEvent = TextDelta | ReasoningDelta | ResponseCompleted


class ProviderError(Exception):
    """Provider 调用失败。``requires_compaction`` 为 Stage 4 的 prompt-too-long 压缩恢复预留。"""

    def __init__(
        self,
        kind: ProviderErrorKind,
        message: str,
        *,
        retryable: bool,
        requires_compaction: bool = False,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable
        self.requires_compaction = requires_compaction


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """Provider 非流式响应：文本 / 推理 / 工具调用 / 用量聚合在单个结果里。"""

    content: str
    reasoning_content: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: ProviderError | None = None


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
class PendingInputInfo:
    request_id: str
    kind: str
    question: str
    options: tuple[str, ...]
    payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "kind": self.kind,
            "question": self.question,
            "options": list(self.options),
            "payload": self.payload,
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
    pending_input: PendingInputInfo | None = None
    model_calls: int = 0
    tool_rounds: int = 0
    context: dict[str, object] | None = None

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
            "pending_input": (None if self.pending_input is None else self.pending_input.to_dict()),
            "model_calls": self.model_calls,
            "tool_rounds": self.tool_rounds,
            "context": self.context,
        }
