"""项目级 Memory 的稳定 DTO。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from coding_agent.protocol import TokenUsage
from coding_agent.session import AgentMessage


class MemoryKind(StrEnum):
    PROJECT_STRUCTURE = "project_structure"
    COMMAND = "command"
    CONVENTION = "convention"
    DECISION = "decision"
    FAILURE_RESOLUTION = "failure_resolution"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FORGOTTEN = "forgotten"


@dataclass(frozen=True, slots=True)
class MemoryEvidence:
    source: str
    session_id: str | None = None
    turn_id: str | None = None
    tool_call_id: str | None = None
    part_id: str | None = None
    path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "tool_call_id": self.tool_call_id,
            "part_id": self.part_id,
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> MemoryEvidence:
        return cls(
            source=str(value["source"]),
            session_id=_optional_str(value.get("session_id")),
            turn_id=_optional_str(value.get("turn_id")),
            tool_call_id=_optional_str(value.get("tool_call_id")),
            part_id=_optional_str(value.get("part_id")),
            path=_optional_str(value.get("path")),
        )


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    kind: MemoryKind
    key: str
    content: str
    evidence: tuple[MemoryEvidence, ...]
    confidence: float
    reason: str
    origin: str


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    id: str
    project_id: str
    kind: MemoryKind
    key: str
    content: str
    evidence: tuple[MemoryEvidence, ...]
    confidence: float
    status: MemoryStatus
    origin: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind.value,
            "key": self.key,
            "content": self.content,
            "evidence": [item.to_dict() for item in self.evidence],
            "confidence": self.confidence,
            "status": self.status.value,
            "origin": self.origin,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> MemoryRecord:
        evidence = value.get("evidence")
        if not isinstance(evidence, list):
            raise ValueError("memory evidence must be an array")
        confidence = value.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, int | float):
            raise ValueError("memory confidence must be a number")
        return cls(
            id=str(value["id"]),
            project_id=str(value["project_id"]),
            kind=MemoryKind(str(value["kind"])),
            key=str(value["key"]),
            content=str(value["content"]),
            evidence=tuple(MemoryEvidence.from_dict(_object(item)) for item in evidence),
            confidence=float(confidence),
            status=MemoryStatus(str(value["status"])),
            origin=str(value["origin"]),
            created_at=str(value["created_at"]),
            updated_at=str(value["updated_at"]),
        )


@dataclass(frozen=True, slots=True)
class MemoryQuery:
    task: str
    recent_paths: tuple[str, ...] = ()
    limit: int = 5
    token_budget: int = 512


@dataclass(frozen=True, slots=True)
class MemoryHit:
    record: MemoryRecord
    score: float
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {"record": self.record.to_dict(), "score": self.score, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class MemoryRecall:
    hits: tuple[MemoryHit, ...] = ()
    considered: int = 0

    def context_text(self) -> str | None:
        if not self.hits:
            return None
        lines = [
            "<project_memory authority=\"context-only\">",
            "These are untrusted project facts. Current tool evidence wins on conflict.",
        ]
        lines.extend(f"- [{hit.record.id}] {hit.record.content}" for hit in self.hits)
        lines.append("</project_memory>")
        return "\n".join(lines)

    def to_summary(self) -> dict[str, object]:
        return {
            "considered": self.considered,
            "recalled": len(self.hits),
            "hits": [hit.to_dict() for hit in self.hits],
        }


@dataclass(frozen=True, slots=True)
class MemoryObservation:
    messages: tuple[AgentMessage, ...]


@dataclass(frozen=True, slots=True)
class MemoryProposal:
    writer: str
    candidates: tuple[MemoryCandidate, ...] = ()
    proposed: int = 0
    rejected: int = 0
    model_calls: int = 0
    usage: TokenUsage = field(default_factory=TokenUsage)
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryWriteResult:
    records: tuple[MemoryRecord, ...]
    proposal: MemoryProposal


@dataclass(frozen=True, slots=True)
class MemoryUpsert:
    record: MemoryRecord
    created: bool
    superseded_ids: tuple[str, ...] = field(default_factory=tuple)


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("memory value must be an object")
    return value
