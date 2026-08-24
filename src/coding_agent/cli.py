from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from typing import Any

from coding_agent import __version__
from coding_agent.app import run_prompt
from coding_agent.config import AppConfig, ConfigurationError, load_config
from coding_agent.protocol import ErrorInfo, TokenUsage, TurnResult, TurnStatus
from coding_agent.providers import (
    ChatProvider,
    FakeProvider,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="A small, explainable CLI coding agent (M1)",
    )
    parser.add_argument("-p", "--prompt", required=True, help="run one prompt and exit")
    parser.add_argument(
        "--provider",
        choices=("fake", "openai-compatible"),
        help="provider adapter (default: CODING_AGENT_PROVIDER or fake)",
    )
    parser.add_argument("--model", help="model name (or CODING_AGENT_MODEL)")
    parser.add_argument("--base-url", help="OpenAI-compatible base URL (or OPENAI_BASE_URL)")
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="environment variable containing the API key",
    )
    parser.add_argument(
        "--no-stream-usage",
        action="store_true",
        help="omit stream_options for services that do not support streamed usage",
    )
    parser.add_argument(
        "--fake-response",
        default="这是 Fake Provider 的 M1 响应。",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--json", action="store_true", help="emit one JSON result on stdout")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            api_key_env=args.api_key_env,
            include_stream_usage=not args.no_stream_usage,
            fake_response=args.fake_response,
        )
    except ConfigurationError as exc:
        return _render_config_error(str(exc), json_mode=args.json)

    provider = _build_provider(config)

    def write_delta(delta: str) -> None:
        print(delta, end="", flush=True)

    result = asyncio.run(
        run_prompt(
            provider,
            prompt=args.prompt,
            model=config.model,
            on_text_delta=None if args.json else write_delta,
        )
    )
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":")))
    else:
        if result.output_text:
            print()
        if result.error is not None:
            print(f"provider error [{result.error.kind}]: {result.error.message}", file=sys.stderr)
    return 0 if result.status is TurnStatus.COMPLETED else 1


def _build_provider(config: AppConfig) -> ChatProvider:
    if config.provider == "fake":
        return FakeProvider(response_text=config.fake_response)
    if config.api_key is None:
        raise AssertionError("validated openai-compatible config is missing api_key")
    return OpenAICompatibleProvider(
        OpenAICompatibleConfig(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            include_stream_usage=config.include_stream_usage,
        )
    )


def _render_config_error(message: str, *, json_mode: bool) -> int:
    if json_mode:
        result = TurnResult(
            schema_version=1,
            session_id="",
            turn_id="",
            status=TurnStatus.FAILED,
            stop_reason="config_error",
            output_text="",
            verified=None,
            verification=(),
            tools_used=(),
            usage=TokenUsage(),
            error=ErrorInfo(kind="config", message=message, retryable=False),
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"configuration error: {message}", file=sys.stderr)
    return 2


def _configure_utf8_stdio() -> None:
    """Keep redirected Windows output and JSON consistently UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure: Any | None = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")
