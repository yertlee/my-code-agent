from __future__ import annotations

import pytest

from coding_agent.app import run_prompt
from coding_agent.protocol import (
    ProviderError,
    ProviderErrorKind,
    TurnStatus,
)
from coding_agent.providers.fake import FakeProvider


@pytest.mark.asyncio
async def test_fake_provider_streams_and_records_request() -> None:
    provider = FakeProvider("abcdef", chunk_size=2)
    seen: list[str] = []

    result = await run_prompt(
        provider,
        prompt="hello",
        model="fake-model",
        on_text_delta=seen.append,
    )

    assert seen == ["ab", "cd", "ef"]
    assert result.status is TurnStatus.COMPLETED
    assert result.output_text == "abcdef"
    assert result.usage.total_tokens == 18
    assert provider.requests[0].messages[-1].content == "hello"


@pytest.mark.asyncio
async def test_provider_error_becomes_failed_turn_result() -> None:
    provider = FakeProvider(
        error=ProviderError(ProviderErrorKind.RATE_LIMIT, "slow down", retryable=True)
    )

    result = await run_prompt(provider, prompt="hello", model="fake-model")

    assert result.status is TurnStatus.FAILED
    assert result.stop_reason == "provider_error"
    assert result.error is not None
    assert result.error.kind == "rate_limit"
    assert result.error.retryable is True


def test_fake_provider_rejects_invalid_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_size"):
        FakeProvider(chunk_size=0)
