from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from typing import Any

from coding_agent import __version__
from coding_agent.config import AppConfig, ConfigurationError, load_config
from coding_agent.protocol import ErrorInfo, TokenUsage, TurnResult, TurnStatus
from coding_agent.providers import (
    ChatProvider,
    FakeProvider,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
    readonly_demo_script,
)
from coding_agent.runtime import RuntimeLimits, RuntimeRunner
from coding_agent.tools import ToolRegistry, readonly_tools
from coding_agent.workspace import Workspace, WorkspaceError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="A small, explainable CLI coding agent (M2 read-only loop)",
    )
    parser.add_argument("-p", "--prompt", required=True, help="run one prompt and exit")
    parser.add_argument(
        "--provider",
        choices=("fake", "openai-compatible"),
        help="provider adapter (default: CODING_AGENT_PROVIDER or fake)",
    )
    parser.add_argument("--model", help="model name (or CODING_AGENT_MODEL)")
    parser.add_argument("--base-url", help="OpenAI-compatible base URL (or OPENAI_BASE_URL)")
    parser.add_argument("--cwd", default=".", help="workspace root (default: current directory)")
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
        default="这是 Fake Provider 的响应。",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--fake-scenario",
        choices=("text", "readonly"),
        default="text",
        help="deterministic fake scenario for demos and tests",
    )
    parser.add_argument("--max-model-calls", type=int, default=8)
    parser.add_argument("--max-tool-rounds", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=120.0, help="turn timeout in seconds")
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
            fake_scenario=args.fake_scenario,
        )
        workspace = Workspace(args.cwd)
        limits = RuntimeLimits(
            max_model_calls=args.max_model_calls,
            max_tool_rounds=args.max_tool_rounds,
            max_turn_seconds=args.timeout,
        )
    except (ConfigurationError, WorkspaceError, ValueError) as exc:
        return _render_config_error(str(exc), json_mode=args.json)

    provider = _build_provider(config)

    def write_delta(delta: str) -> None:
        print(delta, end="", flush=True)

    def write_tool_activity(name: str, activity: str) -> None:
        print(f"[tool] {name} {activity}", file=sys.stderr)

    runner = RuntimeRunner(
        provider=provider,
        model=config.model,
        workspace=workspace,
        tools=ToolRegistry(readonly_tools()),
        limits=limits,
        on_text_delta=None if args.json else write_delta,
        on_tool_activity=None if args.json else write_tool_activity,
    )
    result = asyncio.run(runner.run(args.prompt))
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":")))
    else:
        if result.output_text:
            print()
        if result.error is not None:
            print(f"provider error [{result.error.kind}]: {result.error.message}", file=sys.stderr)
        elif result.status is not TurnStatus.COMPLETED:
            print(f"agent stopped [{result.stop_reason}]", file=sys.stderr)
    if result.status is TurnStatus.COMPLETED:
        return 0
    if result.status in {TurnStatus.LIMITED, TurnStatus.CANCELLED}:
        return 4
    return 1


def _build_provider(config: AppConfig) -> ChatProvider:
    if config.provider == "fake":
        if config.fake_scenario == "readonly":
            final_text = (
                "只读演示完成：Grep 定位到 src/coding_agent/protocol/models.py，"
                "Read 随后读取了该文件开头并确认 ProviderErrorKind 的定义。"
            )
            return FakeProvider(script=readonly_demo_script(final_text))
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
