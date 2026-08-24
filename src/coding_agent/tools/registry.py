from __future__ import annotations

import json

from pydantic import ValidationError

from coding_agent.protocol import ToolCall, ToolDefinition, ToolResult
from coding_agent.tools.base import Tool, ToolContext


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

    async def execute(self, call: ToolCall, context: ToolContext) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return self._error(call, "unknown_tool", f"unknown tool: {call.name}")
        try:
            decoded = json.loads(call.arguments_json)
        except json.JSONDecodeError as exc:
            return self._error(call, "invalid_json", f"invalid tool arguments JSON: {exc.msg}")
        if not isinstance(decoded, dict):
            return self._error(call, "invalid_arguments", "tool arguments must be a JSON object")

        try:
            execution = await tool.execute(decoded, context)
        except ValidationError as exc:
            details = "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
            return self._error(call, "invalid_arguments", details)
        except (OSError, UnicodeError, ValueError) as exc:
            return self._error(call, "tool_error", str(exc))

        content, truncated = self._truncate(execution.content)
        return ToolResult(
            tool_call_id=call.id,
            tool_name=call.name,
            content=content,
            truncated=truncated,
        )

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
