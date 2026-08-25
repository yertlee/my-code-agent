from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from coding_agent.app.factory import build_application
from coding_agent.protocol import TurnResult
from coding_agent.providers.base import ChatProvider
from coding_agent.runtime import EventSink, RuntimeEvent, RuntimeEventKind
from coding_agent.tools import ToolRegistry
from coding_agent.workspace import Workspace


class _CallbackEventSink(EventSink):
    def __init__(self, on_text_delta: Callable[[str], None] | None) -> None:
        self.on_text_delta = on_text_delta

    def emit(self, event: RuntimeEvent) -> None:
        if event.kind is RuntimeEventKind.TEXT_DELTA and self.on_text_delta is not None:
            self.on_text_delta(str(event.payload["text"]))


async def run_prompt(
    provider: ChatProvider,
    *,
    prompt: str,
    model: str,
    on_text_delta: Callable[[str], None] | None = None,
) -> TurnResult:
    """Compatibility facade backed by the application composition root."""
    application = build_application(
        provider=provider,
        model=model,
        workspace=Workspace(Path.cwd()),
        tools=ToolRegistry(),
        event_sink=_CallbackEventSink(on_text_delta),
    )
    try:
        return await application.run(prompt)
    finally:
        await application.aclose()
