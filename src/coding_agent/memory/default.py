"""默认项目事实 Memory：确定性证据写入 + 关键词/新鲜度召回。"""

from __future__ import annotations

import os
import re
from hashlib import sha256
from pathlib import Path

from coding_agent.memory.base import MemoryLedger, MemoryRetriever, MemoryWriter
from coding_agent.memory.models import (
    MemoryCandidate,
    MemoryEvidence,
    MemoryHit,
    MemoryKind,
    MemoryObservation,
    MemoryQuery,
    MemoryRecall,
    MemoryRecord,
    MemoryUpsert,
    MemoryWriteResult,
)
from coding_agent.session import PartKind

_PROJECT_FILES = frozenset(
    {
        "pyproject.toml",
        "package.json",
        "cargo.toml",
        "go.mod",
        "requirements.txt",
        "makefile",
        "readme.md",
    }
)
_TOKENS = re.compile(r"[A-Za-z0-9_.:/-]+|[\u4e00-\u9fff]")


class EvidenceMemoryWriter:
    """只从成功工具结果生成可追踪的项目事实候选。"""

    name = "evidence"

    async def propose(
        self,
        observation: MemoryObservation,
    ) -> tuple[MemoryCandidate, ...]:
        candidates: list[MemoryCandidate] = []
        for message in observation.messages:
            for part in message.parts:
                if part.kind is not PartKind.TOOL_RESULT or part.metadata.get("ok") is not True:
                    continue
                tool_name = _string(part.metadata.get("tool_name"))
                evidence = MemoryEvidence(
                    source="tool_result",
                    session_id=message.session_id,
                    turn_id=message.turn_id,
                    tool_call_id=_string(part.metadata.get("tool_call_id")),
                    path=_string(part.metadata.get("path")),
                )
                if tool_name == "Shell" and part.metadata.get("exit_code") == 0:
                    command = _string(part.metadata.get("command"))
                    if command:
                        candidates.append(
                            MemoryCandidate(
                                kind=MemoryKind.COMMAND,
                                key=f"command:{command.casefold()}",
                                content=f"Verified project command / 已验证项目命令: {command}",
                                evidence=(evidence,),
                                confidence=1.0,
                                reason="successful Shell result",
                                origin=self.name,
                            )
                        )
                elif tool_name == "Read" and evidence.path:
                    filename = Path(evidence.path).name.casefold()
                    if filename in _PROJECT_FILES:
                        candidates.append(
                            MemoryCandidate(
                                kind=MemoryKind.PROJECT_STRUCTURE,
                                key=f"project_file:{evidence.path.casefold()}",
                                content=(
                                    "Project configuration file / 项目配置文件: "
                                    f"{evidence.path}"
                                ),
                                evidence=(evidence,),
                                confidence=1.0,
                                reason="successful read of a project configuration file",
                                origin=self.name,
                            )
                        )
        return tuple(candidates)


class KeywordMemoryRetriever:
    """可解释的关键词、路径和新鲜度排序。"""

    name = "keyword"

    async def recall(
        self,
        query: MemoryQuery,
        records: tuple[MemoryRecord, ...],
    ) -> MemoryRecall:
        query_tokens = _tokenize(query.task)
        scored: list[MemoryHit] = []
        total = max(1, len(records))
        for index, record in enumerate(records):
            record_tokens = _tokenize(f"{record.key} {record.content}")
            overlap = query_tokens & record_tokens
            path_match = any(
                evidence.path in query.recent_paths
                for evidence in record.evidence
                if evidence.path is not None
            )
            if not overlap and not path_match:
                continue
            lexical = len(overlap) / max(1, len(query_tokens))
            path_boost = 0.25 if path_match else 0.0
            recency = 0.05 * ((index + 1) / total)
            score = round(lexical + path_boost + recency, 4)
            reason = (
                f"keyword_overlap={len(overlap)} path_boost={path_boost:.2f} "
                f"recency={recency:.2f}"
            )
            scored.append(MemoryHit(record, score, reason))
        scored.sort(key=lambda hit: (-hit.score, hit.record.id))
        selected: list[MemoryHit] = []
        used_tokens = 0
        for hit in scored:
            estimated = max(1, (len(hit.record.content) + 3) // 4)
            if used_tokens + estimated > query.token_budget:
                continue
            selected.append(hit)
            used_tokens += estimated
            if len(selected) >= query.limit:
                break
        return MemoryRecall(tuple(selected), considered=len(records))


class DefaultMemoryService:
    """AgentLoop 唯一依赖的顶层 MemoryService 默认实现。"""

    def __init__(
        self,
        *,
        project_id: str,
        ledger: MemoryLedger,
        writer: MemoryWriter | None = None,
        retriever: MemoryRetriever | None = None,
    ) -> None:
        self.project_id = project_id
        self.ledger = ledger
        self.writer = writer or EvidenceMemoryWriter()
        self.retriever = retriever or KeywordMemoryRetriever()

    async def recall(self, query: MemoryQuery) -> MemoryRecall:
        return await self.retriever.recall(query, self.ledger.list_records(self.project_id))

    async def observe(self, observation: MemoryObservation) -> MemoryWriteResult:
        candidates = await self.writer.propose(observation)
        records: list[MemoryRecord] = []
        for candidate in candidates:
            upsert = self.ledger.upsert(self.project_id, candidate)
            if upsert.created:
                records.append(upsert.record)
        return MemoryWriteResult(tuple(records), candidates=len(candidates))

    async def remember(self, candidate: MemoryCandidate) -> MemoryUpsert:
        return self.ledger.upsert(self.project_id, candidate)

    async def list_records(
        self,
        *,
        include_inactive: bool = False,
    ) -> tuple[MemoryRecord, ...]:
        return self.ledger.list_records(self.project_id, include_inactive=include_inactive)

    async def get(self, memory_id: str) -> MemoryRecord | None:
        return self.ledger.get(self.project_id, memory_id)

    async def forget(self, memory_id: str) -> bool:
        return self.ledger.forget(self.project_id, memory_id)


def manual_memory_candidate(
    content: str,
    *,
    kind: MemoryKind = MemoryKind.DECISION,
    key: str | None = None,
    evidence: tuple[MemoryEvidence, ...] = (),
) -> MemoryCandidate:
    normalized = content.strip()
    if not normalized:
        raise ValueError("memory content must not be empty")
    resolved_key = key or f"manual:{sha256(normalized.encode('utf-8')).hexdigest()[:16]}"
    return MemoryCandidate(
        kind=kind,
        key=resolved_key,
        content=normalized,
        evidence=evidence or (MemoryEvidence(source="user"),),
        confidence=1.0,
        reason="explicit user memory",
        origin="manual",
    )


def project_id_for(root: str | Path) -> str:
    normalized = os.path.normcase(str(Path(root).resolve(strict=True)))
    return f"project_{sha256(normalized.encode('utf-8')).hexdigest()[:16]}"


def _tokenize(value: str) -> set[str]:
    return {token.casefold() for token in _TOKENS.findall(value)}


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
