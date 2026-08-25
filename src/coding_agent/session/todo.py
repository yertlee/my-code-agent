from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TodoItem:
    id: str
    content: str
    status: str
    blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class TodoPlan:
    revision: int = 0
    items: tuple[TodoItem, ...] = ()


class TodoStore:
    def __init__(self) -> None:
        self._plan = TodoPlan()

    def current(self) -> TodoPlan:
        return self._plan

    def replace(self, *, expected_revision: int, items: tuple[TodoItem, ...]) -> TodoPlan:
        if expected_revision != self._plan.revision:
            raise ValueError(
                f"revision_conflict: expected {expected_revision}, actual {self._plan.revision}"
            )
        self._plan = TodoPlan(revision=self._plan.revision + 1, items=items)
        return self._plan
