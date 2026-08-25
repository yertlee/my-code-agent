from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from coding_agent.app import InteractiveShell, RichEventRenderer, build_application
from coding_agent.providers import FakeProvider
from coding_agent.tools import ToolRegistry
from coding_agent.workspace import Workspace


@pytest.mark.asyncio
async def test_interactive_shell_handles_commands_and_runs_multiple_turns(tmp_path: Path) -> None:
    provider = FakeProvider(response_text="interactive ok", repeat=True)
    output = StringIO()
    console = Console(file=output, force_terminal=False, color_system=None, width=100)
    renderer = RichEventRenderer(console)
    application = build_application(
        provider=provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(),
        event_sink=renderer,
    )
    lines = iter(("/help", "", "first", "/unknown", "second", "/exit"))

    async def read_line(prompt: str) -> str:
        assert prompt == "agent> "
        return next(lines)

    shell = InteractiveShell(application=application, read_line=read_line, console=console)
    exit_code = await shell.run()
    await application.aclose()

    rendered = output.getvalue()
    assert exit_code == 0
    assert "Commands:" in rendered
    assert "unknown command: /unknown" in rendered
    assert rendered.count("interactive ok") == 2
    assert len(provider.requests) == 2
    assert provider.close_calls == 1
