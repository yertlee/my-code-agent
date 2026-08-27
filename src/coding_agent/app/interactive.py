from __future__ import annotations

from collections.abc import Awaitable, Callable

from rich.console import Console

from coding_agent.app.application import AgentApplication
from coding_agent.memory.default import manual_memory_candidate
from coding_agent.protocol import TurnStatus

ReadLine = Callable[[str], Awaitable[str]]

HELP_TEXT = """Commands:
  /help        show this help
  /remember X  save one project fact
  /memory list list active project facts
  /memory inspect ID
               show one project fact with provenance
  /forget ID   forget one project fact
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
        self.console.print("[bold]Coding Agent[/bold] [dim]v0.0.7 interactive CLI[/dim]")
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
            if line.startswith("/remember "):
                await self._remember(line.removeprefix("/remember "))
                continue
            if line == "/memory list":
                await self._list_memory()
                continue
            if line.startswith("/memory inspect "):
                await self._inspect_memory(line.removeprefix("/memory inspect "))
                continue
            if line.startswith("/forget "):
                await self._forget_memory(line.removeprefix("/forget "))
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

    async def _remember(self, content: str) -> None:
        try:
            result = await self.application.remember(manual_memory_candidate(content))
            state = "created" if result.created else "existing"
            self.console.print(f"[green]memory {state}[/green] {result.record.id}")
        except (RuntimeError, ValueError) as exc:
            self.console.print(f"[yellow]{exc}[/yellow]")

    async def _list_memory(self) -> None:
        try:
            records = await self.application.list_memory()
            for record in records:
                self.console.print(f"{record.id}  {record.kind.value}  {record.content}")
        except RuntimeError as exc:
            self.console.print(f"[yellow]{exc}[/yellow]")

    async def _inspect_memory(self, memory_id: str) -> None:
        try:
            record = await self.application.get_memory(memory_id.strip())
            if record is None:
                self.console.print(f"[yellow]unknown memory: {memory_id.strip()}[/yellow]")
                return
            self.console.print_json(data=record.to_dict())
        except RuntimeError as exc:
            self.console.print(f"[yellow]{exc}[/yellow]")

    async def _forget_memory(self, memory_id: str) -> None:
        try:
            forgotten = await self.application.forget_memory(memory_id.strip())
            if forgotten:
                self.console.print(f"[green]memory forgotten[/green] {memory_id.strip()}")
            else:
                self.console.print(f"[yellow]unknown memory: {memory_id.strip()}[/yellow]")
        except RuntimeError as exc:
            self.console.print(f"[yellow]{exc}[/yellow]")


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
