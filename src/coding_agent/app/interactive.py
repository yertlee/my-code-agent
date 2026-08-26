from __future__ import annotations

from collections.abc import Awaitable, Callable

from rich.console import Console

from coding_agent.app.application import AgentApplication
from coding_agent.protocol import TurnStatus

ReadLine = Callable[[str], Awaitable[str]]

HELP_TEXT = """Commands:
  /help        show this help
  /exit        close the current session
  /quit        close the current session"""


class InteractiveShell:
    def __init__(
        self,
        *,
        application: AgentApplication,
        read_line: ReadLine,
        console: Console,
    ) -> None:
        self.application = application
        self.read_line = read_line
        self.console = console

    async def run(self) -> int:
        self.console.print("[bold]Coding Agent[/bold] [dim]v0.0.5 interactive CLI[/dim]")
        self.console.print("Type /help for commands.")
        while True:
            try:
                line = (await self.read_line("agent> ")).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print()
                return 0
            if not line:
                continue
            if line in {"/exit", "/quit"}:
                return 0
            if line == "/help":
                self.console.print(HELP_TEXT)
                continue
            if line.startswith("/"):
                self.console.print(f"[yellow]unknown command: {line}[/yellow]")
                continue

            result = await self.application.run(line)
            while result.status is TurnStatus.WAITING and result.pending_input is not None:
                pending = result.pending_input
                self.console.print(f"[yellow]{pending.question}[/yellow]")
                self.console.print("options: " + ", ".join(pending.options))
                try:
                    answer = await self.read_line("permission> ")
                except (EOFError, KeyboardInterrupt):
                    return 0
                result = await self.application.resume_permission(
                    pending.request_id,
                    _normalize_permission_choice(answer),
                )
            if result.error is not None:
                self.console.print(
                    f"[red]provider error [{result.error.kind}]: {result.error.message}[/red]"
                )
            elif result.status is not TurnStatus.COMPLETED:
                self.console.print(f"[yellow]agent stopped [{result.stop_reason}][/yellow]")


def _normalize_permission_choice(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    aliases = {
        "n": "deny",
        "no": "deny",
        "1": "deny",
        "y": "allow_once",
        "yes": "allow_once",
        "2": "allow_once",
        "allow": "allow_once",
        "once": "allow_once",
        "3": "allow_session",
        "always": "allow_session",
        "session": "allow_session",
    }
    return aliases.get(normalized, normalized)
