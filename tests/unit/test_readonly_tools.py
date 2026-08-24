from __future__ import annotations

from pathlib import Path

import pytest

from coding_agent.protocol import ToolCall
from coding_agent.tools import ToolContext, ToolRegistry, readonly_tools
from coding_agent.workspace import Workspace, WorkspaceError


def make_registry(
    tmp_path: Path, *, max_output_chars: int = 20_000
) -> tuple[ToolRegistry, ToolContext]:
    return (
        ToolRegistry(readonly_tools(), max_output_chars=max_output_chars),
        ToolContext(Workspace(tmp_path)),
    )


@pytest.mark.asyncio
async def test_read_returns_numbered_range_and_supports_empty_file(tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
    (tmp_path / "empty.txt").write_text("", encoding="utf-8")
    registry, context = make_registry(tmp_path)

    result = await registry.execute(
        ToolCall("read_1", "Read", '{"path":"sample.py","start_line":2,"end_line":3}'),
        context,
    )
    empty = await registry.execute(ToolCall("read_2", "Read", '{"path":"empty.txt"}'), context)

    assert result.is_error is False
    assert "2: beta\n3: gamma" in result.content
    assert "[empty file]" in empty.content


@pytest.mark.asyncio
async def test_workspace_rejects_escape_absolute_and_binary_read(tmp_path: Path) -> None:
    (tmp_path / "binary.dat").write_bytes(b"abc\x00def")
    registry, context = make_registry(tmp_path)

    escape = await registry.execute(ToolCall("read_1", "Read", '{"path":"../secret.txt"}'), context)
    binary = await registry.execute(ToolCall("read_2", "Read", '{"path":"binary.dat"}'), context)

    assert escape.is_error is True
    assert "inside the workspace" in escape.content
    assert binary.is_error is True
    assert "binary files" in binary.content
    with pytest.raises(WorkspaceError):
        context.workspace.resolve(str((tmp_path / "binary.dat").resolve()))


@pytest.mark.asyncio
async def test_glob_and_grep_are_sorted_scoped_and_exclude_generated_dirs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("class Target:\n    pass\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("target = 2\n", encoding="utf-8")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "hidden.py").write_text("Target = 3\n", encoding="utf-8")
    registry, context = make_registry(tmp_path)

    globbed = await registry.execute(ToolCall("glob_1", "Glob", '{"pattern":"**/*.py"}'), context)
    grepped = await registry.execute(
        ToolCall(
            "grep_1",
            "Grep",
            '{"query":"target","path":"src","glob":"**/*.py"}',
        ),
        context,
    )

    assert globbed.content.splitlines() == ["src/a.py", "src/b.py"]
    assert grepped.content.splitlines() == [
        "src/a.py:1:class Target:",
        "src/b.py:1:target = 2",
    ]


@pytest.mark.asyncio
async def test_registry_handles_unknown_malformed_invalid_and_truncated_output(
    tmp_path: Path,
) -> None:
    (tmp_path / "long.txt").write_text("x" * 500, encoding="utf-8")
    registry, context = make_registry(tmp_path, max_output_chars=100)

    unknown = await registry.execute(ToolCall("x", "Missing", "{}"), context)
    malformed = await registry.execute(ToolCall("x", "Read", "{"), context)
    invalid = await registry.execute(ToolCall("x", "Read", "[]"), context)
    missing = await registry.execute(ToolCall("x", "Read", "{}"), context)
    extra = await registry.execute(
        ToolCall("x", "Read", '{"path":"long.txt","surprise":true}'), context
    )
    truncated = await registry.execute(ToolCall("x", "Read", '{"path":"long.txt"}'), context)

    assert unknown.is_error and "unknown_tool" in unknown.content
    assert malformed.is_error and "invalid_json" in malformed.content
    assert invalid.is_error and "invalid_arguments" in invalid.content
    assert missing.is_error and "invalid_arguments" in missing.content
    assert extra.is_error and "invalid_arguments" in extra.content
    assert truncated.truncated is True
    assert len(truncated.content) == 100
    assert truncated.content.endswith("...[tool output truncated]")


@pytest.mark.asyncio
async def test_read_line_limit_and_invalid_grep_regex_are_errors(tmp_path: Path) -> None:
    (tmp_path / "many.txt").write_text("\n".join(str(i) for i in range(500)), encoding="utf-8")
    registry, context = make_registry(tmp_path)

    too_many = await registry.execute(
        ToolCall("read", "Read", '{"path":"many.txt","start_line":1,"end_line":401}'),
        context,
    )
    bad_regex = await registry.execute(
        ToolCall("grep", "Grep", '{"query":"[","path":"."}'), context
    )

    assert too_many.is_error and "at most 400 lines" in too_many.content
    assert bad_regex.is_error and "invalid regular expression" in bad_regex.content
