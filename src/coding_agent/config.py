from __future__ import annotations

import os
from dataclasses import dataclass


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


def load_config(
    *,
    provider: str | None,
    model: str | None,
    base_url: str | None,
    api_key_env: str,
    include_stream_usage: bool,
    fake_response: str,
) -> AppConfig:
    selected_provider = provider or os.getenv("CODING_AGENT_PROVIDER", "fake")
    selected_model = model or os.getenv("CODING_AGENT_MODEL")
    selected_base_url = base_url or os.getenv("OPENAI_BASE_URL")

    if selected_provider == "fake":
        return AppConfig(
            provider=selected_provider,
            model=selected_model or "fake-model",
            base_url=None,
            api_key=None,
            include_stream_usage=True,
            fake_response=fake_response,
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
    )
