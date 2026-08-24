from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from coding_agent.protocol import ToolDefinition
from coding_agent.workspace import Workspace


@dataclass(frozen=True, slots=True)
class ToolContext:
    workspace: Workspace


@dataclass(frozen=True, slots=True)
class ToolExecution:
    content: str
    metadata: dict[str, object] = field(default_factory=dict)


class Tool(Protocol):
    definition: ToolDefinition

    async def execute(
        self, arguments: dict[str, object], context: ToolContext
    ) -> ToolExecution: ...
