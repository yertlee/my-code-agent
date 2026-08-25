from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from coding_agent.memory import MemoryRetriever
from coding_agent.protocol import ModelMessage, ModelRequest, ToolDefinition
from coding_agent.session import SessionSnapshot

SYSTEM_GUIDANCE = """You are a local coding agent with read-only repository tools.
Use tools when the answer depends on repository contents. Base repository claims on tool evidence.
Never claim to have read a file you did not inspect. Paths in answers must be workspace-relative."""


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
    workspace_root: Path
    memory: MemoryRetriever
    system_guidance: str = SYSTEM_GUIDANCE

    def build(
        self,
        *,
        model: str,
        snapshot: SessionSnapshot,
        tools: tuple[ToolDefinition, ...],
    ) -> ModelRequest:
        projection = self.memory.retrieve(
            snapshot=snapshot,
            workspace_root=self.workspace_root,
        )
        system_parts = [self.system_guidance]
        if projection.items:
            system_parts.append("Relevant memory:\n" + "\n".join(projection.items))
        messages = (
            ModelMessage(role="system", content="\n\n".join(system_parts)),
            *snapshot.messages,
        )
        return ModelRequest(model=model, messages=messages, tools=tools)
