from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from coding_agent.session import SessionSnapshot


@dataclass(frozen=True, slots=True)
class MemoryProjection:
    items: tuple[str, ...] = ()


class MemoryRetriever(Protocol):
    def retrieve(
        self,
        *,
        snapshot: SessionSnapshot,
        workspace_root: Path,
    ) -> MemoryProjection: ...


class EmptyMemoryRetriever:
    """M3 boundary implementation; durable memory is designed in M7."""

    def retrieve(
        self,
        *,
        snapshot: SessionSnapshot,
        workspace_root: Path,
    ) -> MemoryProjection:
        del snapshot, workspace_root
        return MemoryProjection()
