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
        elif event.kind is RuntimeEventKind.CONTEXT_PROJECTED:
            _render_context_projection(event.payload, stderr=self.stderr)
        elif event.kind is RuntimeEventKind.MEMORY_RECALLED:
            if event.payload.get("recalled"):
                print(f"[memory] recalled={event.payload['recalled']}", file=self.stderr)
        elif event.kind is RuntimeEventKind.MEMORY_WRITTEN:
            print(f"[memory] {_memory_write_text(event.payload)}", file=self.stderr)


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
        elif event.kind is RuntimeEventKind.CONTEXT_PROJECTED:
            summary = _context_projection_text(event.payload)
            if summary is not None:
                self._close_stream()
                self.console.print(f"[dim]context[/dim] {summary}")
        elif event.kind is RuntimeEventKind.MEMORY_RECALLED:
            if event.payload.get("recalled"):
                self.console.print(f"[dim]memory[/dim] recalled={event.payload['recalled']}")
        elif event.kind is RuntimeEventKind.MEMORY_WRITTEN:
            self.console.print(f"[dim]memory[/dim] {_memory_write_text(event.payload)}")
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


def _render_context_projection(payload: dict[str, object], *, stderr: TextIO) -> None:
    summary = _context_projection_text(payload)
    if summary is not None:
        print(f"[context] {summary}", file=stderr)


def _context_projection_text(payload: dict[str, object]) -> str | None:
    compacted = payload.get("compacted_tool_results", 0)
    evicted = payload.get("evicted_turn_count", 0)
    exceeded = payload.get("budget_exceeded", False)
    if not compacted and not evicted and not exceeded:
        return None
    details = [
        f"input={payload.get('input_tokens')}/{payload.get('input_capacity')}",
        f"tool_results_compacted={compacted}",
        f"turns_evicted={evicted}",
    ]
    if exceeded:
        details.append("budget_exceeded")
    return " ".join(details)


def _memory_write_text(payload: dict[str, object]) -> str:
    return (
        f"writer={payload.get('writer')} proposed={payload.get('proposed', 0)} "
        f"accepted={payload.get('accepted', 0)} written={payload.get('count', 0)} "
        f"rejected={payload.get('rejected', 0)}"
    )
