from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from coding_agent.protocol import ModelMessage, ModelRequest, ToolDefinition
from coding_agent.session import SessionSnapshot

SYSTEM_GUIDANCE = """You are a local coding agent operating inside one workspace.
Use repository tools when claims depend on local code.
Inspect relevant files before editing them.
Use Edit for file changes, Shell for commands and verification,
and TodoWrite for non-trivial task state.
Tool calls are validated and permission-gated by the runtime.
Never claim an action ran before its result.
Base completion claims on tool evidence. Paths in answers must be workspace-relative."""


class ContextBuilder(Protocol):
    def build(
        self,
        *,
        model: str,
        snapshot: SessionSnapshot,
        tools: tuple[ToolDefinition, ...],
    ) -> ModelRequest: ...


@dataclass(slots=True)
class BasicContextBuilder:
    system_guidance: str = SYSTEM_GUIDANCE

    def build(
        self,
        *,
        model: str,
        snapshot: SessionSnapshot,
        tools: tuple[ToolDefinition, ...],
    ) -> ModelRequest:
        messages = (
            ModelMessage(role="system", content=self.system_guidance),
            *snapshot.messages,
        )
        return ModelRequest(model=model, messages=messages, tools=tools)
