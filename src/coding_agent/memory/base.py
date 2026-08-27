from __future__ import annotations

from typing import Protocol

from coding_agent.memory.models import (
    MemoryCandidate,
    MemoryObservation,
    MemoryQuery,
    MemoryRecall,
    MemoryRecord,
    MemoryUpsert,
    MemoryWriteResult,
)


class MemoryLedger(Protocol):
    def upsert(self, project_id: str, candidate: MemoryCandidate) -> MemoryUpsert: ...

    def list_records(
        self,
        project_id: str,
        *,
        include_inactive: bool = False,
    ) -> tuple[MemoryRecord, ...]: ...

    def get(self, project_id: str, memory_id: str) -> MemoryRecord | None: ...

    def forget(self, project_id: str, memory_id: str) -> bool: ...


class MemoryWriter(Protocol):
    name: str

    async def propose(
        self,
        observation: MemoryObservation,
    ) -> tuple[MemoryCandidate, ...]: ...


class MemoryRetriever(Protocol):
    name: str

    async def recall(
        self,
        query: MemoryQuery,
        records: tuple[MemoryRecord, ...],
    ) -> MemoryRecall: ...


class MemoryService(Protocol):
    async def recall(self, query: MemoryQuery) -> MemoryRecall: ...

    async def observe(self, observation: MemoryObservation) -> MemoryWriteResult: ...

    async def remember(self, candidate: MemoryCandidate) -> MemoryUpsert: ...

    async def list_records(self, *, include_inactive: bool = False) -> tuple[MemoryRecord, ...]: ...

    async def forget(self, memory_id: str) -> bool: ...
