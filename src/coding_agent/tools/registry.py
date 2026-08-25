from __future__ import annotations

import json

from pydantic import ValidationError

from coding_agent.permissions import PermissionAction, permission_request
from coding_agent.protocol import ToolCall, ToolDefinition, ToolResult
from coding_agent.tools.base import (
    PreparableTool,
    PreparedExecutableTool,
    PreparedToolCall,
    Tool,
    ToolContext,
    ToolExecution,
    ToolExecutionError,
    ToolPreflight,
)


class ToolRegistry:
    def __init__(self, tools: tuple[Tool, ...] = (), *, max_output_chars: int = 20_000) -> None:
        if max_output_chars < 100:
            raise ValueError("max_output_chars must be at least 100")
        self._tools = {tool.definition.name: tool for tool in tools}
        if len(self._tools) != len(tools):
            raise ValueError("tool names must be unique")
        self.max_output_chars = max_output_chars

    @property
    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(tool.definition for tool in self._tools.values())

    async def prepare(
        self,
        call: ToolCall,
        context: ToolContext,
    ) -> PreparedToolCall | ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return self._error(call, "unknown_tool", f"unknown tool: {call.name}")
        decoded = self._decode(call)
        if isinstance(decoded, ToolResult):
            return decoded
        try:
            if isinstance(tool, PreparableTool):
                preflight = await tool.prepare(decoded, context)
            else:
                preflight = ToolPreflight(
                    permission_request=permission_request(
                        PermissionAction.READ,
                        call.name,
                        "read-only tool",
                    )
                )
        except ValidationError as exc:
            return self._validation_error(call, exc)
        except ToolExecutionError as exc:
            return self._error(call, exc.code, str(exc))
        except (OSError, UnicodeError, ValueError) as exc:
            return self._error(call, "tool_error", str(exc))
        return PreparedToolCall(call=call, tool=tool, arguments=decoded, preflight=preflight)

    async def execute_prepared(
        self,
        prepared: PreparedToolCall,
        context: ToolContext,
    ) -> ToolResult:
        try:
            if isinstance(prepared.tool, PreparedExecutableTool):
                execution = await prepared.tool.execute_prepared(prepared, context)
            else:
                execution = await prepared.tool.execute(prepared.arguments, context)
        except ValidationError as exc:
            return self._validation_error(prepared.call, exc)
        except ToolExecutionError as exc:
            return self._error(prepared.call, exc.code, str(exc))
        except (OSError, UnicodeError, ValueError) as exc:
            return self._error(prepared.call, "tool_error", str(exc))
        return self._execution_result(prepared.call, execution)

    async def execute(self, call: ToolCall, context: ToolContext) -> ToolResult:
        prepared = await self.prepare(call, context)
        if isinstance(prepared, ToolResult):
            return prepared
        if prepared.preflight.permission_request.action in {
            PermissionAction.WRITE,
            PermissionAction.DELETE,
            PermissionAction.SHELL,
        }:
            return self._error(
                call,
                "permission_required",
                f"{call.name} must execute through the permission pipeline",
            )
        return await self.execute_prepared(prepared, context)

    def _execution_result(self, call: ToolCall, execution: ToolExecution) -> ToolResult:
        content, budget_truncated = self._truncate(execution.content)
        return ToolResult(
            tool_call_id=call.id,
            tool_name=call.name,
            content=content,
            is_error=execution.is_error,
            truncated=execution.truncated or budget_truncated,
            metadata=execution.metadata,
        )

    def _decode(self, call: ToolCall) -> dict[str, object] | ToolResult:
        try:
            decoded = json.loads(call.arguments_json)
        except json.JSONDecodeError as exc:
            return self._error(call, "invalid_json", f"invalid tool arguments JSON: {exc.msg}")
        if not isinstance(decoded, dict):
            return self._error(call, "invalid_arguments", "tool arguments must be a JSON object")
        return decoded

    def _validation_error(self, call: ToolCall, exc: ValidationError) -> ToolResult:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        return self._error(call, "invalid_arguments", details)

    def _error(self, call: ToolCall, code: str, message: str) -> ToolResult:
        content, truncated = self._truncate(f"ERROR [{code}]: {message}")
        return ToolResult(
            tool_call_id=call.id,
            tool_name=call.name,
            content=content,
            is_error=True,
            truncated=truncated,
        )

    def _truncate(self, content: str) -> tuple[str, bool]:
        if len(content) <= self.max_output_chars:
            return content, False
        marker = "\n...[tool output truncated]"
        return content[: self.max_output_chars - len(marker)] + marker, True
