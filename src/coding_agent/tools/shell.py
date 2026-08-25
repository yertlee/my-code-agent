from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from coding_agent.permissions import PermissionAction, permission_request
from coding_agent.protocol import ToolDefinition
from coding_agent.tools.base import (
    PreparedToolCall,
    ToolContext,
    ToolExecution,
    ToolExecutionError,
    ToolPreflight,
)

_CONTROL_PATTERNS = {
    "pipeline": re.compile(r"\|"),
    "redirection": re.compile(r"[<>]"),
    "variable": re.compile(r"\$[A-Za-z_{]"),
    "subexpression": re.compile(r"\$\(|`"),
}


class ShellArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str = Field(min_length=1)
    cwd: str = "."
    timeout_seconds: float = Field(default=120.0, gt=0, le=900)
    max_output_chars: int = Field(default=20_000, ge=100, le=100_000)


@dataclass(frozen=True, slots=True)
class ShellPlan:
    command: str
    cwd: Path
    relative_cwd: str
    timeout_seconds: float
    max_output_chars: int
    features: tuple[str, ...]


class ShellTool:
    definition = ToolDefinition(
        name="Shell",
        description=(
            "Run a PowerShell command inside the workspace with a timeout and bounded output. "
            "Every standard-mode invocation requires user confirmation."
        ),
        input_schema=ShellArguments.model_json_schema(),
    )

    async def prepare(self, arguments: dict[str, object], context: ToolContext) -> ToolPreflight:
        parsed = ShellArguments.model_validate(arguments)
        cwd = context.workspace.resolve(parsed.cwd)
        if not cwd.is_dir():
            raise ToolExecutionError("invalid_cwd", f"not a directory: {parsed.cwd}")
        features = tuple(
            name for name, pattern in _CONTROL_PATTERNS.items() if pattern.search(parsed.command)
        )
        plan = ShellPlan(
            command=parsed.command,
            cwd=cwd,
            relative_cwd=context.workspace.relative(cwd) or ".",
            timeout_seconds=parsed.timeout_seconds,
            max_output_chars=parsed.max_output_chars,
            features=features,
        )
        return ToolPreflight(
            permission_request=permission_request(
                PermissionAction.SHELL,
                parsed.command,
                "execute PowerShell command",
                cwd=plan.relative_cwd,
                timeout_seconds=plan.timeout_seconds,
                features=list(features),
            ),
            preview={
                "command": plan.command,
                "cwd": plan.relative_cwd,
                "timeout_seconds": plan.timeout_seconds,
                "features": list(features),
            },
            opaque=plan,
        )

    async def execute_prepared(
        self,
        prepared: PreparedToolCall,
        context: ToolContext,
    ) -> ToolExecution:
        del context
        plan = prepared.preflight.opaque
        if not isinstance(plan, ShellPlan):
            raise ToolExecutionError("internal_error", "missing trusted Shell plan")
        return await _run_powershell(plan)

    async def execute(self, arguments: dict[str, object], context: ToolContext) -> ToolExecution:
        del arguments, context
        raise ToolExecutionError(
            "permission_required",
            "Shell must execute through an approved prepared call",
        )


async def _run_powershell(plan: ShellPlan) -> ToolExecution:
    executable = shutil.which("pwsh") or shutil.which("powershell.exe")
    if executable is None:
        raise ToolExecutionError("powershell_unavailable", "PowerShell executable was not found")
    process = await asyncio.create_subprocess_exec(
        executable,
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        plan.command,
        cwd=plan.cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    timed_out = False
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=plan.timeout_seconds,
        )
    except TimeoutError:
        timed_out = True
        await _terminate_process_tree(process)
        stdout_bytes, stderr_bytes = await process.communicate()
    except asyncio.CancelledError:
        await _terminate_process_tree(process)
        await process.communicate()
        raise

    stdout, stdout_truncated = _decode_and_truncate(stdout_bytes, plan.max_output_chars)
    stderr, stderr_truncated = _decode_and_truncate(stderr_bytes, plan.max_output_chars)
    exit_code = process.returncode
    lines = [
        f"command: {plan.command}",
        f"cwd: {plan.relative_cwd}",
        f"exit_code: {exit_code}",
    ]
    if stdout:
        lines.extend(("stdout:", stdout))
    if stderr:
        lines.extend(("stderr:", stderr))
    if timed_out:
        lines.append(f"ERROR [timeout]: command exceeded {plan.timeout_seconds} seconds")
    return ToolExecution(
        content="\n".join(lines),
        metadata={
            "command": plan.command,
            "cwd": plan.relative_cwd,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "timed_out": timed_out,
        },
        is_error=timed_out or exit_code != 0,
        truncated=stdout_truncated or stderr_truncated,
    )


async def _terminate_process_tree(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    taskkill = shutil.which("taskkill.exe") or shutil.which("taskkill")
    if taskkill is not None and process.pid is not None:
        killer = await asyncio.create_subprocess_exec(
            taskkill,
            "/PID",
            str(process.pid),
            "/T",
            "/F",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await killer.wait()
    if process.returncode is None:
        process.kill()


def _decode_and_truncate(data: bytes, limit: int) -> tuple[str, bool]:
    text = data.decode("utf-8", errors="replace").rstrip()
    if len(text) <= limit:
        return text, False
    marker = "\n...[output truncated]"
    return text[: limit - len(marker)] + marker, True
