from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from coding_agent.agent import AgentLoop, RuntimeLimits
from coding_agent.context import BasicContextBuilder
from coding_agent.memory import EmptyMemoryRetriever
from coding_agent.permissions import ReadOnlyPermissionPolicy
from coding_agent.protocol import (
    ModelRequest,
    ModelStreamEvent,
    ResponseCompleted,
    ToolCall,
    TurnStatus,
)
from coding_agent.providers import FakeProvider, FakeResponse
from coding_agent.runtime import RecordingEventSink, RuntimeEventKind
from coding_agent.session import InMemorySessionStore
from coding_agent.tools import ToolContext, ToolRegistry, readonly_tools
from coding_agent.workspace import Workspace


def make_loop(
    tmp_path: Path,
    provider: FakeProvider | SlowProvider,
    *,
    limits: RuntimeLimits | None = None,
    events: RecordingEventSink | None = None,
) -> AgentLoop:
    workspace = Workspace(tmp_path)
    return AgentLoop(
        provider=provider,
        model="fake-model",
        session_store=InMemorySessionStore(),
        context_builder=BasicContextBuilder(
            workspace_root=workspace.root,
            memory=EmptyMemoryRetriever(),
        ),
        permission_policy=ReadOnlyPermissionPolicy(),
        tool_context=ToolContext(workspace),
        tools=ToolRegistry(readonly_tools()),
        limits=limits,
        event_sink=events,
    )


@pytest.mark.asyncio
async def test_agent_loop_executes_tools_replays_reasoning_and_emits_events(
    tmp_path: Path,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "demo.py").write_text(
        "class Target:\n    pass\n",
        encoding="utf-8",
    )
    provider = FakeProvider(
        script=(
            FakeResponse(
                reasoning_content="search first",
                tool_calls=(
                    ToolCall(
                        "grep_1",
                        "Grep",
                        '{"query":"Target","path":"src","glob":"**/*.py"}',
                    ),
                ),
            ),
            FakeResponse(
                tool_calls=(
                    ToolCall(
                        "read_1",
                        "Read",
                        '{"path":"src/demo.py","start_line":1,"end_line":2}',
                    ),
                )
            ),
            FakeResponse(text="Target is defined in src/demo.py:1."),
        )
    )
    events = RecordingEventSink()

    result = await make_loop(tmp_path, provider, events=events).run("find Target")

    assert result.status is TurnStatus.COMPLETED
    assert result.tools_used == ("Grep", "Read")
    assert result.model_calls == 3
    assert result.tool_rounds == 2
    second_request = provider.requests[1]
    assert second_request.messages[-2].reasoning_content == "search first"
    assert second_request.messages[-1].role == "tool"
    assert "src/demo.py:1:class Target:" in (second_request.messages[-1].content or "")
    assert [event.kind for event in events.events] == [
        RuntimeEventKind.TURN_STARTED,
        RuntimeEventKind.TOOL_STARTED,
        RuntimeEventKind.TOOL_COMPLETED,
        RuntimeEventKind.TOOL_STARTED,
        RuntimeEventKind.TOOL_COMPLETED,
        RuntimeEventKind.TEXT_DELTA,
        RuntimeEventKind.TEXT_DELTA,
        RuntimeEventKind.TEXT_DELTA,
        RuntimeEventKind.TEXT_DELTA,
        RuntimeEventKind.TEXT_DELTA,
        RuntimeEventKind.TEXT_DELTA,
        RuntimeEventKind.TEXT_DELTA,
        RuntimeEventKind.TEXT_DELTA,
        RuntimeEventKind.TEXT_DELTA,
        RuntimeEventKind.TURN_FINISHED,
    ]


@pytest.mark.asyncio
async def test_agent_loop_stops_at_model_and_tool_round_limits(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    call = ToolCall("read", "Read", '{"path":"file.txt"}')
    model_limited = FakeProvider(script=(FakeResponse(tool_calls=(call,)),))
    tool_limited = FakeProvider(
        script=(FakeResponse(tool_calls=(call,)), FakeResponse(tool_calls=(call,)))
    )

    model_result = await make_loop(
        tmp_path,
        model_limited,
        limits=RuntimeLimits(max_model_calls=1, max_tool_rounds=2),
    ).run("read")
    tool_result = await make_loop(
        tmp_path,
        tool_limited,
        limits=RuntimeLimits(max_model_calls=3, max_tool_rounds=1),
    ).run("read twice")

    assert model_result.status is TurnStatus.LIMITED
    assert model_result.stop_reason == "model_call_limit"
    assert tool_result.status is TurnStatus.LIMITED
    assert tool_result.stop_reason == "tool_round_limit"


@pytest.mark.asyncio
async def test_read_only_policy_denies_other_tool_before_registry(tmp_path: Path) -> None:
    provider = FakeProvider(
        script=(
            FakeResponse(tool_calls=(ToolCall("edit", "Edit", "{}"),)),
            FakeResponse(text="The write tool is unavailable."),
        )
    )

    result = await make_loop(tmp_path, provider).run("edit a file")

    assert result.status is TurnStatus.COMPLETED
    tool_message = provider.requests[1].messages[-1]
    assert tool_message.role == "tool"
    assert "permission_denied" in (tool_message.content or "")


class SlowProvider:
    def __init__(self) -> None:
        self.close_calls = 0

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        del request
        await asyncio.sleep(0.05)
        yield ResponseCompleted()

    async def aclose(self) -> None:
        self.close_calls += 1


@pytest.mark.asyncio
async def test_agent_loop_timeout_and_cancellation_do_not_own_provider_lifecycle(
    tmp_path: Path,
) -> None:
    timed_provider = SlowProvider()
    timed_result = await make_loop(
        tmp_path,
        timed_provider,
        limits=RuntimeLimits(max_turn_seconds=0.01),
    ).run("wait")

    cancelled_provider = SlowProvider()
    task = asyncio.create_task(make_loop(tmp_path, cancelled_provider).run("wait"))
    await asyncio.sleep(0)
    task.cancel()
    cancelled_result = await task

    assert timed_result.status is TurnStatus.LIMITED
    assert timed_result.stop_reason == "turn_timeout"
    assert cancelled_result.status is TurnStatus.CANCELLED
    assert cancelled_result.stop_reason == "cancelled"
    assert timed_provider.close_calls == 0
    assert cancelled_provider.close_calls == 0
