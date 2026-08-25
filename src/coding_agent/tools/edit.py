from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass
from difflib import unified_diff
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from coding_agent.permissions import PermissionAction, permission_request
from coding_agent.protocol import ToolDefinition
from coding_agent.tools.base import (
    PreparedToolCall,
    ToolContext,
    ToolExecution,
    ToolExecutionError,
    ToolPreflight,
)


class EditArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["create", "replace", "delete"]
    path: str = Field(min_length=1)
    old_text: str | None = None
    new_text: str | None = None
    replace_all: bool = False

    @model_validator(mode="after")
    def validate_operation(self) -> EditArguments:
        if self.operation == "create" and self.new_text is None:
            raise ValueError("create requires new_text")
        if self.operation == "replace":
            if not self.old_text:
                raise ValueError("replace requires non-empty old_text")
            if self.new_text is None:
                raise ValueError("replace requires new_text")
        return self


@dataclass(frozen=True, slots=True)
class EditPreview:
    path: Path
    relative_path: str
    operation: str
    before_digest: str | None
    after_text: str | None
    diff: str
    added_lines: int
    removed_lines: int

    def payload(self) -> dict[str, object]:
        return {
            "path": self.relative_path,
            "operation": self.operation,
            "before_digest": self.before_digest,
            "after_digest": _text_digest(self.after_text),
            "diff": self.diff,
            "added_lines": self.added_lines,
            "removed_lines": self.removed_lines,
        }


class EditTool:
    definition = ToolDefinition(
        name="Edit",
        description=(
            "Create, exactly replace text in, or delete one UTF-8 file. "
            "Changes are previewed and permission-gated before execution."
        ),
        input_schema=EditArguments.model_json_schema(),
    )

    async def prepare(self, arguments: dict[str, object], context: ToolContext) -> ToolPreflight:
        parsed = EditArguments.model_validate(arguments)
        target = context.workspace.resolve(parsed.path, must_exist=False)
        if not target.parent.exists() or not target.parent.is_dir():
            raise ToolExecutionError(
                "parent_missing",
                f"parent directory does not exist: {parsed.path}",
            )
        before: str | None
        if target.exists():
            if not target.is_file():
                raise ToolExecutionError("not_a_file", f"not a file: {parsed.path}")
            before = _read_utf8(target)
        else:
            before = None

        if parsed.operation == "create":
            if before is not None:
                raise ToolExecutionError("already_exists", f"file already exists: {parsed.path}")
            after = parsed.new_text
        elif parsed.operation == "replace":
            if before is None:
                raise ToolExecutionError("not_found", f"file does not exist: {parsed.path}")
            old_text = parsed.old_text or ""
            count = before.count(old_text)
            if count == 0:
                raise ToolExecutionError("old_text_not_found", "old_text was not found")
            if count > 1 and not parsed.replace_all:
                raise ToolExecutionError(
                    "ambiguous_match",
                    f"old_text occurs {count} times; make it unique or set replace_all",
                )
            if parsed.replace_all:
                after = before.replace(old_text, parsed.new_text or "")
            else:
                after = before.replace(old_text, parsed.new_text or "", 1)
        else:
            if before is None:
                raise ToolExecutionError("not_found", f"file does not exist: {parsed.path}")
            after = None

        relative = context.workspace.relative(target)
        diff, added, removed = _make_diff(relative, before, after)
        preview = EditPreview(
            path=target,
            relative_path=relative,
            operation=parsed.operation,
            before_digest=_path_digest(target),
            after_text=after,
            diff=diff,
            added_lines=added,
            removed_lines=removed,
        )
        action = PermissionAction.DELETE if parsed.operation == "delete" else PermissionAction.WRITE
        request = permission_request(
            action,
            str(target),
            f"{parsed.operation} file {relative}",
            path=relative,
            operation=parsed.operation,
        )
        return ToolPreflight(permission_request=request, preview=preview.payload(), opaque=preview)

    async def execute_prepared(
        self,
        prepared: PreparedToolCall,
        context: ToolContext,
    ) -> ToolExecution:
        del context
        preview = prepared.preflight.opaque
        if not isinstance(preview, EditPreview):
            raise ToolExecutionError("internal_error", "missing trusted Edit preview")
        if _path_digest(preview.path) != preview.before_digest:
            raise ToolExecutionError(
                "stale_snapshot",
                f"file changed after preview: {preview.relative_path}",
            )
        if preview.operation == "delete":
            preview.path.unlink()
        else:
            _atomic_write(preview.path, preview.after_text or "")
        return ToolExecution(
            content=(
                f"{preview.operation} completed: {preview.relative_path}\n"
                f"added_lines: {preview.added_lines}\nremoved_lines: {preview.removed_lines}"
            ),
            metadata=preview.payload(),
        )

    async def execute(self, arguments: dict[str, object], context: ToolContext) -> ToolExecution:
        del arguments, context
        raise ToolExecutionError(
            "permission_required",
            "Edit must execute through an approved prepared call",
        )


def _read_utf8(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" in data[:4096]:
        raise ToolExecutionError("binary_file", f"binary files are not supported: {path}")
    return data.decode("utf-8")


def _path_digest(path: Path) -> str | None:
    if not path.exists():
        return None
    return sha256(path.read_bytes()).hexdigest()


def _text_digest(text: str | None) -> str | None:
    return None if text is None else sha256(text.encode("utf-8")).hexdigest()


def _make_diff(path: str, before: str | None, after: str | None) -> tuple[str, int, int]:
    lines = list(
        unified_diff(
            (before or "").splitlines(),
            (after or "").splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
    )
    added = sum(line.startswith("+") and not line.startswith("+++") for line in lines)
    removed = sum(line.startswith("-") and not line.startswith("---") for line in lines)
    return "\n".join(lines), added, removed


def _atomic_write(path: Path, content: str) -> None:
    previous_mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if previous_mode is not None:
            os.chmod(temp_name, previous_mode)
        os.replace(temp_name, path)
        temp_name = None
    finally:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)
