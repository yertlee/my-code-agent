from __future__ import annotations

from pathlib import Path

import pytest

from coding_agent.agent import AgentLoop
from coding_agent.context import BudgetedContextBuilder
from coding_agent.memory.default import (
    DefaultMemoryService,
    EvidenceMemoryWriter,
    KeywordMemoryRetriever,
    manual_memory_candidate,
)
from coding_agent.memory.jsonl import JsonlMemoryLedger
from coding_agent.memory.models import (
    MemoryKind,
    MemoryObservation,
    MemoryQuery,
    MemoryStatus,
)
from coding_agent.permissions import PermissionManager
from coding_agent.protocol import TokenUsage, ToolCall, ToolResult
from coding_agent.providers import FakeProvider, FakeResponse
from coding_agent.session import (
    InMemorySessionStore,
    SessionSnapshot,
    tool_result_message,
    user_message,
)
from coding_agent.tools import ToolContext, ToolRegistry, readonly_tools
from coding_agent.workspace import Workspace


def test_jsonl_memory_upsert_supersede_and_forget(tmp_path: Path) -> None:
    ledger = JsonlMemoryLedger(tmp_path)
    first = ledger.upsert(
        "project_1",
        manual_memory_candidate("Tests use pytest", key="test.command"),
    )
    duplicate = ledger.upsert(
        "project_1",
        manual_memory_candidate("Tests use pytest", key="test.command"),
    )
    replacement = ledger.upsert(
        "project_1",
        manual_memory_candidate("Tests use uv run pytest", key="test.command"),
    )

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.record.id == first.record.id
    assert replacement.superseded_ids == (first.record.id,)
    assert ledger.list_records("project_1") == (replacement.record,)
    inactive = ledger.list_records("project_1", include_inactive=True)
    assert inactive[0].status is MemoryStatus.SUPERSEDED

    assert ledger.forget("project_1", replacement.record.id) is True
    assert ledger.list_records("project_1") == ()
    forgotten = ledger.get("project_1", replacement.record.id)
    assert forgotten is not None
    assert forgotten.status is MemoryStatus.FORGOTTEN


@pytest.mark.asyncio
async def test_evidence_writer_records_successful_shell_and_project_file() -> None:
    shell = tool_result_message(
        "ses_1",
        ToolResult(
            "call_1",
            "Shell",
            "exit_code: 0",
            metadata={"command": "uv run pytest", "exit_code": 0},
        ),
        turn_id="turn_1",
    )
    project_file = tool_result_message(
        "ses_1",
        ToolResult(
            "call_2",
            "Read",
            "path: pyproject.toml",
            metadata={"path": "pyproject.toml"},
        ),
        turn_id="turn_1",
    )

    candidates = await EvidenceMemoryWriter().propose(
        MemoryObservation((shell, project_file))
    )

    assert [candidate.kind for candidate in candidates] == [
        MemoryKind.COMMAND,
        MemoryKind.PROJECT_STRUCTURE,
    ]
    assert candidates[0].content.endswith("已验证项目命令: uv run pytest")
    assert candidates[0].evidence[0].tool_call_id == "call_1"


@pytest.mark.asyncio
async def test_keyword_recall_is_explainable_and_context_is_low_authority(
    tmp_path: Path,
) -> None:
    service = DefaultMemoryService(
        project_id="project_1",
        ledger=JsonlMemoryLedger(tmp_path),
        retriever=KeywordMemoryRetriever(),
    )
    await service.remember(
        manual_memory_candidate("Tests use uv run pytest", key="test.command")
    )
    await service.remember(
        manual_memory_candidate("项目使用 uv 管理依赖", key="dependency.manager")
    )

    recall = await service.recall(MemoryQuery(task="run project tests"))
    chinese_recall = await service.recall(MemoryQuery(task="项目如何管理依赖"))

    assert len(recall.hits) == 1
    assert "keyword_overlap" in recall.hits[0].reason
    assert chinese_recall.hits[0].record.key == "dependency.manager"
    snapshot = SessionSnapshot(
        "ses_1",
        (user_message("ses_1", "run project tests", turn_id="turn_1"),),
        TokenUsage(),
    )
    request = BudgetedContextBuilder().build(
        model="demo",
        snapshot=snapshot,
        tools=(),
        memory=recall,
    )
    assert request.messages[0].role == "system"
    assert request.messages[1].role == "user"
    assert "authority=\"context-only\"" in (request.messages[1].content or "")
    assert request.messages[2].content == "run project tests"
    assert snapshot.messages[0].parts[0].content == "run project tests"


@pytest.mark.asyncio
async def test_agent_loop_writes_tool_evidence_and_new_session_recalls_it(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    service = DefaultMemoryService(
        project_id="project_1",
        ledger=JsonlMemoryLedger(tmp_path / ".memory"),
    )
    first_provider = FakeProvider(
        script=(
            FakeResponse(
                tool_calls=(ToolCall("read_1", "Read", '{"path":"pyproject.toml"}'),)
            ),
            FakeResponse(text="found"),
        )
    )
    first_loop = AgentLoop(
        provider=first_provider,
        model="fake-model",
        session_store=InMemorySessionStore(),
        context_builder=BudgetedContextBuilder(),
        permission_manager=PermissionManager(),
        tool_context=ToolContext(Workspace(tmp_path)),
        tools=ToolRegistry(readonly_tools()),
        memory_service=service,
    )

    first_result = await first_loop.run("inspect project config")
    second_provider = FakeProvider(response_text="recalled")
    second_loop = AgentLoop(
        provider=second_provider,
        model="fake-model",
        session_store=InMemorySessionStore(),
        context_builder=BudgetedContextBuilder(),
        permission_manager=PermissionManager(),
        tool_context=ToolContext(Workspace(tmp_path)),
        tools=ToolRegistry(),
        memory_service=service,
    )
    second_result = await second_loop.run("where is the project configuration file")

    records = await service.list_records()
    assert first_result.memory is not None
    assert first_result.memory["written"] == 1
    assert records[0].content.endswith("项目配置文件: pyproject.toml")
    assert second_result.memory is not None
    assert second_result.memory["recalled"] == 1
    assert "project_memory" in (second_provider.requests[0].messages[1].content or "")
