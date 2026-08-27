"""Append-only JSONL project memory ledger。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from coding_agent.memory.models import (
    MemoryCandidate,
    MemoryRecord,
    MemoryStatus,
    MemoryUpsert,
)

MEMORY_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class _MemoryEvent:
    kind: str
    project_id: str
    payload: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": MEMORY_SCHEMA_VERSION,
            "kind": self.kind,
            "project_id": self.project_id,
            "created_at": _now(),
            "payload": self.payload,
        }


class JsonlMemoryLedger:
    """以单个 JSONL 账本保存项目事实与状态迁移。"""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve(strict=False)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "memory.jsonl"

    def upsert(self, project_id: str, candidate: MemoryCandidate) -> MemoryUpsert:
        records = self.list_records(project_id)
        matching = tuple(record for record in records if record.key == candidate.key)
        for record in matching:
            if record.content == candidate.content:
                return MemoryUpsert(record=record, created=False)
        superseded_ids: list[str] = []
        for record in matching:
            self._append(
                _MemoryEvent(
                    "status_changed",
                    project_id,
                    {"memory_id": record.id, "status": MemoryStatus.SUPERSEDED.value},
                )
            )
            superseded_ids.append(record.id)
        timestamp = _now()
        record = MemoryRecord(
            id=f"mem_{uuid4().hex}",
            project_id=project_id,
            kind=candidate.kind,
            key=candidate.key,
            content=candidate.content,
            evidence=candidate.evidence,
            confidence=candidate.confidence,
            status=MemoryStatus.ACTIVE,
            origin=candidate.origin,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._append(_MemoryEvent("record_added", project_id, {"record": record.to_dict()}))
        return MemoryUpsert(record, True, tuple(superseded_ids))

    def list_records(
        self,
        project_id: str,
        *,
        include_inactive: bool = False,
    ) -> tuple[MemoryRecord, ...]:
        records = self._replay().values()
        selected = tuple(record for record in records if record.project_id == project_id)
        if include_inactive:
            return selected
        return tuple(record for record in selected if record.status is MemoryStatus.ACTIVE)

    def get(self, project_id: str, memory_id: str) -> MemoryRecord | None:
        record = self._replay().get(memory_id)
        return record if record is not None and record.project_id == project_id else None

    def forget(self, project_id: str, memory_id: str) -> bool:
        record = self.get(project_id, memory_id)
        if record is None or record.status is MemoryStatus.FORGOTTEN:
            return False
        self._append(
            _MemoryEvent(
                "status_changed",
                project_id,
                {"memory_id": memory_id, "status": MemoryStatus.FORGOTTEN.value},
            )
        )
        return True

    def _replay(self) -> dict[str, MemoryRecord]:
        records: dict[str, MemoryRecord] = {}
        if not self.path.exists():
            return records
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                event = json.loads(line)
                if event.get("schema_version") != MEMORY_SCHEMA_VERSION:
                    raise ValueError("unsupported memory schema_version")
                payload = event["payload"]
                if not isinstance(payload, dict):
                    raise ValueError("memory payload must be an object")
                if event["kind"] == "record_added":
                    value = payload["record"]
                    if not isinstance(value, dict):
                        raise ValueError("memory record must be an object")
                    record = MemoryRecord.from_dict(value)
                    records[record.id] = record
                elif event["kind"] == "status_changed":
                    memory_id = str(payload["memory_id"])
                    record = records[memory_id]
                    records[memory_id] = replace(
                        record,
                        status=MemoryStatus(str(payload["status"])),
                        updated_at=str(event["created_at"]),
                    )
                else:
                    raise ValueError("unknown memory event kind")
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"corrupt memory log at line {line_number}: {exc}") from exc
        return records

    def _append(self, event: _MemoryEvent) -> None:
        encoded = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
