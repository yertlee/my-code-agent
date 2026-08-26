from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from coding_agent.permissions import PermissionRequest
from coding_agent.protocol import ToolCall, ToolDefinition
from coding_agent.workspace import Workspace


@dataclass(frozen=True, slots=True)
class ToolContext:
    workspace: Workspace


@dataclass(frozen=True, slots=True)
class ToolExecution:
    content: str
    metadata: dict[str, object] = field(default_factory=dict)
    is_error: bool = False
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class ToolPreflight:
    permission_request: PermissionRequest
    preview: dict[str, object] | None = None
    opaque: object | None = None


@dataclass(frozen=True, slots=True)
class PreparedToolCall:
    call: ToolCall
    tool: Tool
    arguments: dict[str, object]
    preflight: ToolPreflight


class ToolExecutionError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class Tool(Protocol):
    definition: ToolDefinition

    async def execute(
        self, arguments: dict[str, object], context: ToolContext
    ) -> ToolExecution: ...


@runtime_checkable
class PreparableTool(Protocol):
    async def prepare(
        self,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> ToolPreflight: ...


@runtime_checkable
class PreparedExecutableTool(Protocol):
    async def execute_prepared(
        self,
        prepared: PreparedToolCall,
        context: ToolContext,
    ) -> ToolExecution: ...
