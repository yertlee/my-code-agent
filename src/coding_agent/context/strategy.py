from __future__ import annotations

from typing import Protocol

from coding_agent.context.budget import ContextBudget
from coding_agent.context.compaction import CompactionResult, ContextCompactor
from coding_agent.session import SessionSnapshot


class ContextStrategy(Protocol):
    """在预算内把 Session facts 投影成临时事实视图。"""

    name: str

    def project(
        self,
        snapshot: SessionSnapshot,
        budget: ContextBudget,
    ) -> CompactionResult: ...


class DeterministicContextStrategy:
    """默认 L1/L2/L3 策略：确定性、可重放、不修改事实账本。"""

    name = "deterministic"

    def __init__(self, compactor: ContextCompactor | None = None) -> None:
        self.compactor = compactor or ContextCompactor()

    def project(
        self,
        snapshot: SessionSnapshot,
        budget: ContextBudget,
    ) -> CompactionResult:
        return self.compactor.compact(snapshot, budget)
