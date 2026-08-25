"""Cooperative cancellation primitives shared by the CLI, agent, and tools."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


class AgentCancelledError(RuntimeError):
    """Raised when a running turn observes user cancellation."""


@dataclass(slots=True)
class CancellationToken:
    """Small thread-safe cancellation flag."""

    _event: threading.Event = field(default_factory=threading.Event)

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise AgentCancelledError("agent turn was cancelled")
