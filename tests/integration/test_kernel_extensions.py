from __future__ import annotations

from pathlib import Path

import pytest

from coding_agent.app import build_application
from coding_agent.protocol import ToolCall, ToolDefinition, TurnStatus
from coding_agent.providers import FakeProvider, FakeResponse
from coding_agent.tools import ToolContext, ToolExecution, ToolRegistry
from coding_agent.workspace import Workspace


class EchoTool:
    definition = ToolDefinition(
        name="Echo",
        description="Return one text argument.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    )

    async def execute(
        self,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> ToolExecution:
        del context
        return ToolExecution(content=f"echo: {arguments['text']}")


@pytest.mark.asyncio
async def test_custom_tool_mounts_without_agent_loop_changes(tmp_path: Path) -> None:
    provider = FakeProvider(
        script=(
            FakeResponse(
                tool_calls=(ToolCall("echo_1", "Echo", '{"text":"plugin works"}'),)
            ),
            FakeResponse(text="extension completed"),
        )
    )
    application = build_application(
        provider=provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry((EchoTool(),)),
    )

    result = await application.run("use the extension")
    await application.aclose()

    assert result.status is TurnStatus.COMPLETED
    assert result.output_text == "extension completed"
    assert result.tools_used == ("Echo",)
    assert provider.requests[1].messages[-1].content == "echo: plugin works"
