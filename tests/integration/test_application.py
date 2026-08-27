from __future__ import annotations

from pathlib import Path

import pytest

from coding_agent.app import build_application
from coding_agent.providers import FakeProvider
from coding_agent.session import InMemorySessionStore
from coding_agent.tools import ToolRegistry
from coding_agent.workspace import Workspace


@pytest.mark.asyncio
async def test_application_reuses_session_across_turns_and_closes_provider_once(
    tmp_path: Path,
) -> None:
    provider = FakeProvider(response_text="ack", repeat=True)
    store = InMemorySessionStore()
    application = build_application(
        provider=provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(),
        session_store=store,
    )

    first = await application.run("first")
    second = await application.run("second")
    await application.aclose()
    await application.aclose()

    assert first.session_id == second.session_id
    assert first.turn_id != second.turn_id
    assert [message.role for message in provider.requests[1].messages] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert provider.requests[1].messages[-3].content == "first"
    assert provider.requests[1].messages[-2].content == "ack"
    assert provider.requests[1].messages[-1].content == "second"
    assert provider.close_calls == 1

    facts = store.snapshot(first.session_id).messages
    assert [message.role for message in facts] == ["user", "assistant", "user", "assistant"]
    assert facts[0].parts[0].content == "first"
    assert facts[1].parts[0].content == "ack"
    assert facts[2].parts[0].content == "second"
