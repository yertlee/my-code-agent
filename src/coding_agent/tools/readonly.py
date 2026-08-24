from __future__ import annotations

import fnmatch
import re
from pathlib import Path, PurePath

from pydantic import BaseModel, ConfigDict, Field

from coding_agent.protocol import ToolDefinition
from coding_agent.tools.base import ToolContext, ToolExecution

MAX_TEXT_FILE_BYTES = 2_000_000


class ReadArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)


class GlobArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern: str = Field(min_length=1)
    path: str = "."
    max_results: int = Field(default=100, ge=1, le=200)


class GrepArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    path: str = "."
    glob: str = "**/*"
    case_sensitive: bool = False
    max_results: int = Field(default=100, ge=1, le=200)


class ReadTool:
    definition = ToolDefinition(
        name="Read",
        description="Read a UTF-8 text file with stable 1-based line numbers.",
        input_schema=ReadArguments.model_json_schema(),
    )

    async def execute(self, arguments: dict[str, object], context: ToolContext) -> ToolExecution:
        parsed = ReadArguments.model_validate(arguments)
        path = context.workspace.resolve(parsed.path)
        if not path.is_file():
            raise ValueError(f"not a file: {parsed.path}")
        if path.stat().st_size > MAX_TEXT_FILE_BYTES:
            raise ValueError(f"file exceeds {MAX_TEXT_FILE_BYTES} byte read limit")
        text = _read_text(path)
        lines = text.splitlines()
        relative = context.workspace.relative(path)
        if not lines:
            return ToolExecution(f"path: {relative}\nlines: 0\n[empty file]")
        end_line = parsed.end_line or min(len(lines), parsed.start_line + 399)
        if end_line < parsed.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        if end_line - parsed.start_line + 1 > 400:
            raise ValueError("Read supports at most 400 lines per call")
        selected = lines[parsed.start_line - 1 : end_line]
        body = "\n".join(
            f"{line_number}: {line}"
            for line_number, line in enumerate(selected, start=parsed.start_line)
        )
        header = f"path: {relative}\nlines: {parsed.start_line}-{end_line}"
        return ToolExecution(f"{header}\n{body}" if body else f"{header}\n[no lines]")


class GlobTool:
    definition = ToolDefinition(
        name="Glob",
        description="List files matching a glob pattern inside the workspace.",
        input_schema=GlobArguments.model_json_schema(),
    )

    async def execute(self, arguments: dict[str, object], context: ToolContext) -> ToolExecution:
        parsed = GlobArguments.model_validate(arguments)
        _validate_pattern(parsed.pattern)
        matches: list[str] = []
        for path in context.workspace.walk_files(parsed.path):
            relative = context.workspace.relative(path)
            scoped = _relative_to_search_root(relative, parsed.path)
            if _glob_matches(scoped, parsed.pattern):
                matches.append(relative)
                if len(matches) >= parsed.max_results:
                    break
        return ToolExecution("\n".join(matches) if matches else "[no matches]")


class GrepTool:
    definition = ToolDefinition(
        name="Grep",
        description=(
            "Search UTF-8 text files using a regular expression and return path:line evidence."
        ),
        input_schema=GrepArguments.model_json_schema(),
    )

    async def execute(self, arguments: dict[str, object], context: ToolContext) -> ToolExecution:
        parsed = GrepArguments.model_validate(arguments)
        _validate_pattern(parsed.glob)
        flags = 0 if parsed.case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(parsed.query, flags)
        except re.error as exc:
            raise ValueError(f"invalid regular expression: {exc}") from exc

        matches: list[str] = []
        for path in context.workspace.walk_files(parsed.path):
            relative = context.workspace.relative(path)
            scoped = _relative_to_search_root(relative, parsed.path)
            if not _glob_matches(scoped, parsed.glob) or path.stat().st_size > MAX_TEXT_FILE_BYTES:
                continue
            try:
                text = _read_text(path)
            except (UnicodeError, ValueError):
                continue
            for line_number, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    matches.append(f"{relative}:{line_number}:{line}")
                    if len(matches) >= parsed.max_results:
                        return ToolExecution("\n".join(matches))
        return ToolExecution("\n".join(matches) if matches else "[no matches]")


def readonly_tools() -> tuple[ReadTool | GlobTool | GrepTool, ...]:
    return (ReadTool(), GlobTool(), GrepTool())


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" in data[:4096]:
        raise ValueError("binary files are not supported")
    return data.decode("utf-8")


def _validate_pattern(pattern: str) -> None:
    pure = PurePath(pattern)
    if pure.is_absolute() or pure.drive or ".." in pure.parts:
        raise ValueError(f"glob pattern must stay inside the workspace: {pattern}")


def _glob_matches(relative: str, pattern: str) -> bool:
    normalized = relative.replace("\\", "/")
    normalized_pattern = pattern.replace("\\", "/")
    if fnmatch.fnmatchcase(normalized, normalized_pattern):
        return True
    if normalized_pattern.startswith("**/"):
        return fnmatch.fnmatchcase(normalized, normalized_pattern[3:])
    return False


def _relative_to_search_root(relative: str, search_root: str) -> str:
    normalized_root = search_root.replace("\\", "/").rstrip("/")
    while normalized_root.startswith("./"):
        normalized_root = normalized_root[2:]
    if normalized_root in {"", "."}:
        return relative
    prefix = normalized_root.rstrip("/") + "/"
    return relative[len(prefix) :] if relative.startswith(prefix) else relative
