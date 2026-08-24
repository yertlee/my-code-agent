from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from coding_agent.protocol import (
    ModelRequest,
    ModelStreamEvent,
    ResponseCompleted,
    ToolCall,
    TurnStatus,
)
from coding_agent.providers import FakeProvider, FakeResponse
from coding_agent.runtime import RuntimeLimits, RuntimeRunner
from coding_agent.tools import ToolRegistry, readonly_tools
from coding_agent.workspace import Workspace


def make_runner(
    tmp_path: Path,
    provider: FakeProvider,
    *,
    limits: RuntimeLimits | None = None,
) -> RuntimeRunner:
    return RuntimeRunner(
        provider=provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(readonly_tools()),
        limits=limits,
    )


@pytest.mark.asyncio
async def test_runner_executes_tool_loop_and_replays_reasoning(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "demo.py").write_text("class Target:\n    pass\n", encoding="utf-8")
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

    result = await make_runner(tmp_path, provider).run("find Target")

    assert result.status is TurnStatus.COMPLETED
    assert result.tools_used == ("Grep", "Read")
    assert result.model_calls == 3
    assert result.tool_rounds == 2
    second_request = provider.requests[1]
    assert second_request.messages[-2].reasoning_content == "search first"
    assert second_request.messages[-1].role == "tool"
    assert "src/demo.py:1:class Target:" in (second_request.messages[-1].content or "")


@pytest.mark.asyncio
async def test_runner_stops_at_model_and_tool_round_limits(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    call = ToolCall("read", "Read", '{"path":"file.txt"}')
    model_limited = FakeProvider(script=(FakeResponse(tool_calls=(call,)),))
    tool_limited = FakeProvider(
        script=(FakeResponse(tool_calls=(call,)), FakeResponse(tool_calls=(call,)))
    )

    model_result = await make_runner(
        tmp_path,
        model_limited,
        limits=RuntimeLimits(max_model_calls=1, max_tool_rounds=2),
    ).run("read")
    tool_result = await make_runner(
        tmp_path,
        tool_limited,
        limits=RuntimeLimits(max_model_calls=3, max_tool_rounds=1),
    ).run("read twice")

    assert model_result.status is TurnStatus.LIMITED
    assert model_result.stop_reason == "model_call_limit"
    assert tool_result.status is TurnStatus.LIMITED
    assert tool_result.stop_reason == "tool_round_limit"


class SlowProvider:
    def __init__(self) -> None:
        self.closed = False

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        del request
        await asyncio.sleep(0.05)
        yield ResponseCompleted()

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_runner_has_hard_turn_timeout(tmp_path: Path) -> None:
    provider = SlowProvider()
    runner = RuntimeRunner(
        provider=provider,
        model="slow-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(),
        limits=RuntimeLimits(max_turn_seconds=0.01),
    )

    result = await runner.run("wait")

    assert result.status is TurnStatus.LIMITED
    assert result.stop_reason == "turn_timeout"
    assert provider.closed is True


@pytest.mark.asyncio
async def test_runner_turns_external_cancellation_into_terminal_result(tmp_path: Path) -> None:
    provider = SlowProvider()
    runner = RuntimeRunner(
        provider=provider,
        model="slow-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(),
    )

    task = asyncio.create_task(runner.run("wait"))
    await asyncio.sleep(0)
    task.cancel()
    result = await task

    assert result.status is TurnStatus.CANCELLED
    assert result.stop_reason == "cancelled"
    assert provider.closed is True
