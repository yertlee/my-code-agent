from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from coding_agent.permissions import PermissionAction, permission_request
from coding_agent.protocol import ToolDefinition
from coding_agent.session import TodoItem, TodoStore
from coding_agent.tools.base import ToolContext, ToolExecution, ToolExecutionError, ToolPreflight


class TodoItemArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    status: Literal["pending", "in_progress", "completed", "blocked"]
    blocked_reason: str | None = None

    @model_validator(mode="after")
    def validate_blocked(self) -> TodoItemArguments:
        if self.status == "blocked" and not self.blocked_reason:
            raise ValueError("blocked item requires blocked_reason")
        return self


class TodoWriteArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=0)
    items: list[TodoItemArguments] = Field(max_length=100)

    @model_validator(mode="after")
    def validate_plan(self) -> TodoWriteArguments:
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("todo ids must be unique")
        if sum(item.status == "in_progress" for item in self.items) > 1:
            raise ValueError("at most one todo may be in_progress")
        return self


class TodoWriteTool:
    definition = ToolDefinition(
        name="TodoWrite",
        description=(
            "Replace the current in-memory todo snapshot using optimistic revision control."
        ),
        input_schema=TodoWriteArguments.model_json_schema(),
    )

    def __init__(self, store: TodoStore | None = None) -> None:
        self.store = store or TodoStore()

    async def prepare(self, arguments: dict[str, object], context: ToolContext) -> ToolPreflight:
        del context
        TodoWriteArguments.model_validate(arguments)
        return ToolPreflight(
            permission_request=permission_request(
                PermissionAction.SESSION_STATE,
                "todos",
                "update todo snapshot",
            )
        )

    async def execute(self, arguments: dict[str, object], context: ToolContext) -> ToolExecution:
        del context
        parsed = TodoWriteArguments.model_validate(arguments)
        items = tuple(
            TodoItem(
                id=item.id,
                content=item.content,
                status=item.status,
                blocked_reason=item.blocked_reason,
            )
            for item in parsed.items
        )
        try:
            plan = self.store.replace(expected_revision=parsed.expected_revision, items=items)
        except ValueError as exc:
            raise ToolExecutionError("revision_conflict", str(exc)) from exc
        lines = [f"revision: {plan.revision}"]
        lines.extend(f"{item.id} [{item.status}] {item.content}" for item in plan.items)
        return ToolExecution("\n".join(lines))
