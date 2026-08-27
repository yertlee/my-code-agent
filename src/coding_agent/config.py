from __future__ import annotations

import os
from dataclasses import dataclass

from coding_agent.context.budget import DEFAULT_CONTEXT_WINDOW


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AppConfig:
    provider: str
    model: str
    base_url: str | None
    api_key: str | None
    include_stream_usage: bool
    fake_response: str
    fake_scenario: str
    context_window: int


def context_window_env() -> int:
    """读取 ``CODING_AGENT_CONTEXT_WINDOW`` 覆盖默认上下文窗口（产品决策 #1）。

    优先级：CLI 参数（Stage 5）> 环境变量 > 默认 32k（产品决策 #9）。
    启动时解析一次。非法值抛 ``ConfigurationError``。
    """
    raw = os.getenv("CODING_AGENT_CONTEXT_WINDOW")
    if raw is None:
        return DEFAULT_CONTEXT_WINDOW
    return _context_window_value(raw, source="CODING_AGENT_CONTEXT_WINDOW")


def load_config(
    *,
    provider: str | None,
    model: str | None,
    base_url: str | None,
    api_key_env: str,
    include_stream_usage: bool,
    fake_response: str,
    fake_scenario: str = "text",
    context_window: int | None = None,
) -> AppConfig:
    selected_provider = provider or os.getenv("CODING_AGENT_PROVIDER", "fake")
    selected_model = model or os.getenv("CODING_AGENT_MODEL")
    selected_base_url = base_url or os.getenv("OPENAI_BASE_URL")
    selected_context_window = (
        context_window_env()
        if context_window is None
        else _context_window_value(str(context_window), source="--context-window")
    )

    if selected_provider == "fake":
        return AppConfig(
            provider=selected_provider,
            model=selected_model or "fake-model",
            base_url=None,
            api_key=None,
            include_stream_usage=True,
            fake_response=fake_response,
            fake_scenario=fake_scenario,
            context_window=selected_context_window,
        )

    if not selected_model:
        raise ConfigurationError(
            "openai-compatible provider requires --model or CODING_AGENT_MODEL"
        )
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise ConfigurationError(
            f"openai-compatible provider requires the {api_key_env} environment variable"
        )
    return AppConfig(
        provider=selected_provider,
        model=selected_model,
        base_url=selected_base_url,
        api_key=api_key,
        include_stream_usage=include_stream_usage,
        fake_response=fake_response,
        fake_scenario=fake_scenario,
        context_window=selected_context_window,
    )


def _context_window_value(raw: str, *, source: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{source} must be an integer, got: {raw!r}") from exc
    if value < 1:
        raise ConfigurationError(f"{source} must be positive")
    return value
