from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeLimits:
    max_model_calls: int = 8
    max_tool_rounds: int = 6
    max_turn_seconds: float = 120.0

    def __post_init__(self) -> None:
        if self.max_model_calls < 1:
            raise ValueError("max_model_calls must be at least 1")
        if self.max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1")
        if self.max_turn_seconds <= 0:
            raise ValueError("max_turn_seconds must be positive")
