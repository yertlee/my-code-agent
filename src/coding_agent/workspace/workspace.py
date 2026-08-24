from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path, PurePath


class WorkspaceError(ValueError):
    pass


DEFAULT_EXCLUDED_DIRS = frozenset(
    {".git", ".venv", ".coding-agent", "__pycache__", ".pytest_cache", "build", "dist"}
)


class Workspace:
    def __init__(self, root: str | Path) -> None:
        candidate = Path(root).expanduser()
        if not candidate.exists() or not candidate.is_dir():
            raise WorkspaceError(f"workspace root is not a directory: {candidate}")
        self.root = candidate.resolve(strict=True)
        self._root_norm = os.path.normcase(str(self.root))

    def resolve(self, relative_path: str, *, must_exist: bool = True) -> Path:
        if not relative_path or not relative_path.strip():
            raise WorkspaceError("path must not be empty")
        raw = PurePath(relative_path)
        if raw.is_absolute() or raw.drive or ".." in raw.parts:
            raise WorkspaceError(f"path must stay inside the workspace: {relative_path}")

        candidate = (self.root / Path(relative_path)).resolve(strict=must_exist)
        candidate_norm = os.path.normcase(str(candidate))
        try:
            common = os.path.commonpath((self._root_norm, candidate_norm))
        except ValueError as exc:
            raise WorkspaceError(f"path must stay inside the workspace: {relative_path}") from exc
        if common != self._root_norm:
            raise WorkspaceError(f"path must stay inside the workspace: {relative_path}")
        return candidate

    def relative(self, path: Path) -> str:
        resolved = path.resolve(strict=False)
        self._ensure_resolved_inside(resolved)
        return resolved.relative_to(self.root).as_posix()

    def walk_files(self, start: str = ".") -> Iterator[Path]:
        start_path = self.resolve(start)
        if not start_path.is_dir():
            raise WorkspaceError(f"search path is not a directory: {start}")
        for current, directories, filenames in os.walk(start_path):
            directories[:] = sorted(
                name for name in directories if name not in DEFAULT_EXCLUDED_DIRS
            )
            current_path = Path(current)
            for filename in sorted(filenames):
                path = current_path / filename
                try:
                    self._ensure_resolved_inside(path.resolve(strict=True))
                except (OSError, WorkspaceError):
                    continue
                yield path

    def _ensure_resolved_inside(self, path: Path) -> None:
        path_norm = os.path.normcase(str(path))
        try:
            common = os.path.commonpath((self._root_norm, path_norm))
        except ValueError as exc:
            raise WorkspaceError(f"resolved path escapes workspace: {path}") from exc
        if common != self._root_norm:
            raise WorkspaceError(f"resolved path escapes workspace: {path}")
