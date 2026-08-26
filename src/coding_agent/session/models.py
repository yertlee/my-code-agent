from __future__ import annotations

from dataclasses import dataclass

from coding_agent.permissions import PermissionRequest
from coding_agent.protocol import ModelMessage, TokenUsage, ToolCall


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    session_id: str
    messages: tuple[ModelMessage, ...]
    usage: TokenUsage


@dataclass(frozen=True, slots=True)
class TurnIdentity:
    session_id: str
    turn_id: str


@dataclass(frozen=True, slots=True)
class PendingPermission:
    identity: TurnIdentity
    call: ToolCall
    remaining_calls: tuple[ToolCall, ...]
    request: PermissionRequest
    preview: dict[str, object] | None
    confirmation_fingerprint: str
    tools_used: tuple[str, ...]
    usage: TokenUsage
    model_calls: int
    tool_rounds: int
    last_output_text: str
