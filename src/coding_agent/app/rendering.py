from __future__ import annotations

import sys
from typing import TextIO

from rich.console import Console
from rich.text import Text

from coding_agent.runtime import EventSink, RuntimeEvent, RuntimeEventKind


class PlainEventRenderer(EventSink):
    """Stable one-shot renderer used by scripts and compatibility tests."""

    def __init__(self, *, stdout: TextIO | None = None, stderr: TextIO | None = None) -> None:
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr

    def emit(self, event: RuntimeEvent) -> None:
        if event.kind is RuntimeEventKind.TEXT_DELTA:
            self.stdout.write(str(event.payload["text"]))
            self.stdout.flush()
        elif event.kind is RuntimeEventKind.TOOL_STARTED:
            print(f"[tool] {event.payload['tool_name']} started", file=self.stderr)
        elif event.kind is RuntimeEventKind.TOOL_COMPLETED:
            status = "failed" if event.payload["is_error"] else "completed"
            print(f"[tool] {event.payload['tool_name']} {status}", file=self.stderr)
        elif event.kind is RuntimeEventKind.DIFF_READY:
            preview = event.payload.get("preview")
            if isinstance(preview, dict) and preview.get("diff"):
                print("[diff]", file=self.stderr)
                print(preview["diff"], file=self.stderr)


class RichEventRenderer(EventSink):
    """Interactive activity renderer; domain state stays inside AgentLoop."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self._stream_open = False

    def emit(self, event: RuntimeEvent) -> None:
        if event.kind is RuntimeEventKind.TURN_STARTED:
            self.console.print(f"[dim]turn {event.turn_id[-8:]} started[/dim]")
        elif event.kind is RuntimeEventKind.TEXT_DELTA:
            self.console.print(Text(str(event.payload["text"])), end="")
            self._stream_open = True
        elif event.kind is RuntimeEventKind.TOOL_STARTED:
            self._close_stream()
            self.console.print(f"[cyan]tool[/cyan] {event.payload['tool_name']} [dim]started[/dim]")
        elif event.kind is RuntimeEventKind.DIFF_READY:
            self._close_stream()
            preview = event.payload.get("preview")
            if isinstance(preview, dict):
                self.console.print(
                    f"[bold]diff[/bold] {preview.get('operation', '')} {preview.get('path', '')}"
                )
                if preview.get("diff"):
                    self.console.print(Text(str(preview["diff"])))
        elif event.kind is RuntimeEventKind.TOOL_COMPLETED:
            self._close_stream()
            style = "red" if event.payload["is_error"] else "green"
            status = "failed" if event.payload["is_error"] else "completed"
            self.console.print(
                f"[{style}]tool[/{style}] {event.payload['tool_name']} [dim]{status}[/dim]"
            )
        elif event.kind is RuntimeEventKind.TURN_FINISHED:
            self._close_stream()
            if event.payload["status"] != "completed":
                self.console.print(
                    f"[yellow]turn stopped: {event.payload['stop_reason']}[/yellow]"
                )

    def _close_stream(self) -> None:
        if self._stream_open:
            self.console.print()
            self._stream_open = False
