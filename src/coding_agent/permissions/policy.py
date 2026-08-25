from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from coding_agent.protocol import ToolCall


class PermissionVerdict(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    verdict: PermissionVerdict
    reason: str


class PermissionPolicy(Protocol):
    def decide(self, call: ToolCall) -> PermissionDecision: ...


class ReadOnlyPermissionPolicy:
    """M3 policy that only admits the three read-only built-ins."""

    allowed_tools = frozenset({"Read", "Glob", "Grep"})

    def decide(self, call: ToolCall) -> PermissionDecision:
        if call.name in self.allowed_tools:
            return PermissionDecision(PermissionVerdict.ALLOW, "read-only built-in")
        return PermissionDecision(
            PermissionVerdict.DENY,
            f"tool is not available in read-only mode: {call.name}",
        )
