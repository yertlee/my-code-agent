from coding_agent.tools.base import (
    PreparedToolCall,
    Tool,
    ToolContext,
    ToolExecution,
    ToolExecutionError,
    ToolPreflight,
)
from coding_agent.tools.edit import EditTool
from coding_agent.tools.readonly import GlobTool, GrepTool, ReadTool, readonly_tools
from coding_agent.tools.registry import ToolRegistry
from coding_agent.tools.shell import ShellTool
from coding_agent.tools.todo import TodoWriteTool

__all__ = [
    "EditTool",
    "GlobTool",
    "GrepTool",
    "PreparedToolCall",
    "ReadTool",
    "ShellTool",
    "Tool",
    "ToolContext",
    "ToolExecution",
    "ToolExecutionError",
    "ToolPreflight",
    "ToolRegistry",
    "TodoWriteTool",
    "readonly_tools",
]


def coding_tools() -> tuple[
    ReadTool | GlobTool | GrepTool | EditTool | ShellTool | TodoWriteTool,
    ...,
]:
    return (*readonly_tools(), EditTool(), ShellTool(), TodoWriteTool())


__all__.append("coding_tools")
