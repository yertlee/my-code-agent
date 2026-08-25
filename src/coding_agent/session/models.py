from __future__ import annotations

from dataclasses import dataclass

from coding_agent.protocol import ModelMessage, TokenUsage


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    session_id: str
    messages: tuple[ModelMessage, ...]
    usage: TokenUsage


@dataclass(frozen=True, slots=True)
class TurnIdentity:
    session_id: str
    turn_id: str
