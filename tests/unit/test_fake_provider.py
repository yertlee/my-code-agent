from __future__ import annotations

import pytest

from coding_agent.app import build_application
from coding_agent.protocol import (
    ProviderError,
    ProviderErrorKind,
    TurnStatus,
)
from coding_agent.providers.fake import FakeProvider
from coding_agent.runtime import RecordingEventSink, RuntimeEventKind
from coding_agent.tools import ToolRegistry
from coding_agent.workspace import Workspace


@pytest.mark.asyncio
async def test_fake_provider_streams_and_records_request(tmp_path) -> None:
    provider = FakeProvider("abcdef", chunk_size=2)
    events = RecordingEventSink()
    application = build_application(
        provider=provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(),
        event_sink=events,
    )
    result = await application.run("hello")
    await application.aclose()

    seen = [
        str(event.payload["text"])
        for event in events.events
        if event.kind is RuntimeEventKind.TEXT_DELTA
    ]

    assert seen == ["ab", "cd", "ef"]
    assert result.status is TurnStatus.COMPLETED
    assert result.output_text == "abcdef"
    assert result.usage.total_tokens == 18
    assert provider.requests[0].messages[-1].content == "hello"


@pytest.mark.asyncio
async def test_provider_error_becomes_failed_turn_result(tmp_path) -> None:
    provider = FakeProvider(
        error=ProviderError(ProviderErrorKind.RATE_LIMIT, "slow down", retryable=True)
    )

    application = build_application(
        provider=provider,
        model="fake-model",
        workspace=Workspace(tmp_path),
        tools=ToolRegistry(),
    )
    result = await application.run("hello")
    await application.aclose()

    assert result.status is TurnStatus.FAILED
    assert result.stop_reason == "provider_error"
    assert result.error is not None
    assert result.error.kind == "rate_limit"
    assert result.error.retryable is True


def test_fake_provider_rejects_invalid_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        FakeProvider(chunk_size=0)
