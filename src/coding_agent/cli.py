from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console

from coding_agent import __version__
from coding_agent.agent import RuntimeLimits
from coding_agent.app import (
    AgentApplication,
    InteractiveShell,
    PlainEventRenderer,
    ReadLine,
    RichEventRenderer,
    build_application,
)
from coding_agent.config import AppConfig, ConfigurationError, load_config
from coding_agent.protocol import ErrorInfo, TokenUsage, TurnResult, TurnStatus
from coding_agent.providers import (
    ChatProvider,
    FakeProvider,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
    readonly_demo_script,
)
from coding_agent.runtime import NullEventSink
from coding_agent.tools import ToolRegistry, readonly_tools
from coding_agent.workspace import Workspace, WorkspaceError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="A small, explainable CLI coding agent",
    )
    parser.add_argument("-p", "--prompt", help="run one prompt and exit")
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
    if args.json and args.prompt is None:
        return _render_config_error("--json requires -p/--prompt", json_mode=True)
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
    if args.prompt is not None:
        renderer = NullEventSink() if args.json else PlainEventRenderer()
        application = build_application(
            provider=provider,
            model=config.model,
            workspace=workspace,
            tools=ToolRegistry(readonly_tools()),
            limits=limits,
            event_sink=renderer,
        )
        return asyncio.run(_run_one_shot(application, args.prompt, json_mode=args.json))

    console = Console()
    renderer = RichEventRenderer(console)
    application = build_application(
        provider=provider,
        model=config.model,
        workspace=workspace,
        tools=ToolRegistry(readonly_tools()),
        limits=limits,
        event_sink=renderer,
    )
    shell = InteractiveShell(
        application=application,
        read_line=_build_read_line(),
        console=console,
    )
    return asyncio.run(_run_interactive(application, shell))


async def _run_one_shot(
    application: AgentApplication,
    prompt: str,
    *,
    json_mode: bool,
) -> int:
    try:
        result = await application.run(prompt)
    finally:
        await application.aclose()
    if json_mode:
        print(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":")))
    else:
        if result.output_text:
            print()
        if result.error is not None:
            print(f"provider error [{result.error.kind}]: {result.error.message}", file=sys.stderr)
        elif result.status is not TurnStatus.COMPLETED:
            print(f"agent stopped [{result.stop_reason}]", file=sys.stderr)
    return _exit_code(result)


async def _run_interactive(application: AgentApplication, shell: InteractiveShell) -> int:
    try:
        return await shell.run()
    finally:
        await application.aclose()


def _build_read_line() -> ReadLine:
    if sys.stdin.isatty():
        try:
            prompt_session: PromptSession[str] = PromptSession(history=InMemoryHistory())
        except Exception:
            return _read_console_line
        return prompt_session.prompt_async
    return _read_redirected_line


async def _read_console_line(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def _read_redirected_line(prompt: str) -> str:
    del prompt
    line = await asyncio.to_thread(sys.stdin.readline)
    if line == "":
        raise EOFError
    return line


def _exit_code(result: TurnResult) -> int:
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
        return FakeProvider(response_text=config.fake_response, repeat=True)
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
