"""config 模块：环境变量窗口覆盖的单元测试。"""

from __future__ import annotations

import pytest

from coding_agent.config import (
    ConfigurationError,
    context_window_env,
    load_config,
)
from coding_agent.context import DEFAULT_CONTEXT_WINDOW


def test_context_window_env_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODING_AGENT_CONTEXT_WINDOW", raising=False)
    assert context_window_env() == DEFAULT_CONTEXT_WINDOW


def test_context_window_env_reads_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODING_AGENT_CONTEXT_WINDOW", "16384")
    assert context_window_env() == 16_384


def test_context_window_env_rejects_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODING_AGENT_CONTEXT_WINDOW", "not-a-number")
    with pytest.raises(ConfigurationError, match="must be an integer"):
        context_window_env()

    monkeypatch.setenv("CODING_AGENT_CONTEXT_WINDOW", "0")
    with pytest.raises(ConfigurationError, match="must be positive"):
        context_window_env()


def test_load_config_carries_context_window_into_app_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CODING_AGENT_CONTEXT_WINDOW", raising=False)
    config = load_config(
        provider="fake",
        model=None,
        base_url=None,
        api_key_env="OPENAI_API_KEY",
        include_stream_usage=True,
        fake_response="x",
    )
    assert config.context_window == DEFAULT_CONTEXT_WINDOW

    config = load_config(
        provider="fake",
        model=None,
        base_url=None,
        api_key_env="OPENAI_API_KEY",
        include_stream_usage=True,
        fake_response="x",
        context_window=8192,
    )
    assert config.context_window == 8_192
