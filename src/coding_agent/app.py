from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from coding_agent.protocol import TurnResult
from coding_agent.providers.base import ChatProvider
from coding_agent.runtime import RuntimeRunner
from coding_agent.tools import ToolRegistry
from coding_agent.workspace import Workspace


async def run_prompt(
    provider: ChatProvider,
    *,
    prompt: str,
    model: str,
    on_text_delta: Callable[[str], None] | None = None,
) -> TurnResult:
    """M1-compatible one-call facade backed by the sole RuntimeRunner."""
    runner = RuntimeRunner(
        provider=provider,
        model=model,
        workspace=Workspace(Path.cwd()),
        tools=ToolRegistry(),
        on_text_delta=on_text_delta,
    )
    return await runner.run(prompt)
