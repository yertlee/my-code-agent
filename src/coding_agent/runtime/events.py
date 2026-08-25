"""Ephemeral runtime activity observed by terminal renderers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class RuntimeEventKind(StrEnum):
    TURN_STARTED = "turn_started"
    TEXT_DELTA = "text_delta"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TURN_FINISHED = "turn_finished"


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    kind: RuntimeEventKind
    session_id: str
    turn_id: str
    payload: dict[str, object] = field(default_factory=dict)


class EventSink(Protocol):
    def emit(self, event: RuntimeEvent) -> None: ...


class NullEventSink:
    def emit(self, event: RuntimeEvent) -> None:
        del event


class RecordingEventSink:
    """Useful for diagnostics and deterministic tests."""

    def __init__(self) -> None:
        self.events: list[RuntimeEvent] = []

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)
