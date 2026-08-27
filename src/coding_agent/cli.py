from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Sequence

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console

from coding_agent.agent import RuntimeLimits
from coding_agent.app import (
    AgentApplication,
    InteractiveShell,
    PlainEventRenderer,
    ReadLine,
    RichEventRenderer,
    build_application,
)
from coding_agent.app.arguments import build_parser
from coding_agent.app.cli_output import (
    configure_utf8_stdio,
    render_config_error,
    render_turn_result,
)
from coding_agent.app.memory_commands import run_memory_command
from coding_agent.app.session_commands import (
    resolve_waiting,
    resume_session,
    session_summaries,
    validate_session_options,
)
from coding_agent.config import AppConfig, ConfigurationError, load_config
from coding_agent.memory.assisted import StructuredExtractionWriter
from coding_agent.memory.default import DefaultMemoryService, project_id_for
from coding_agent.memory.jsonl import JsonlMemoryLedger
from coding_agent.memory.models import MemoryKind
from coding_agent.permissions import PermissionMode
from coding_agent.providers import (
    ChatProvider,
    FakeProvider,
    FakeResponse,
    OpenAICompatibleConfig,
    OpenAICompatibleProvider,
    readonly_demo_script,
    write_demo_script,
)
from coding_agent.runtime import NullEventSink
from coding_agent.session import JsonlSessionStore
from coding_agent.tools import ToolRegistry, coding_tools
from coding_agent.workspace import Workspace, WorkspaceError


def main(argv: Sequence[str] | None = None) -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    argument_error = validate_session_options(
        prompt=args.prompt,
        resume=args.resume,
        list_sessions=args.list_sessions,
        json_mode=args.json,
        permission_choice=args.permission_choice,
        session_dir=args.session_dir,
        remember=args.remember,
        list_memory=args.list_memory,
        inspect_memory=args.inspect_memory,
        forget_memory=args.forget_memory,
        memory_dir=args.memory_dir,
        memory_key=args.memory_key,
        memory_writer=args.memory_writer,
    )
    if argument_error is not None:
        return render_config_error(argument_error, json_mode=args.json)
    try:
        workspace = Workspace(args.cwd)
        session_store = (
            None
            if args.session_dir is None
            else JsonlSessionStore(workspace.resolve(args.session_dir, must_exist=False))
        )
        memory_service = (
            None
            if args.memory_dir is None
            else DefaultMemoryService(
                project_id=project_id_for(workspace.root),
                ledger=JsonlMemoryLedger(
                    workspace.resolve(args.memory_dir, must_exist=False)
                ),
            )
        )
        if args.list_sessions:
            if session_store is None:
                raise AssertionError("validated session listing is missing its store")
            return _render_session_list(session_store, json_mode=args.json)
        if any(
            (
                args.remember is not None,
                args.list_memory,
                args.inspect_memory is not None,
                args.forget_memory is not None,
            )
        ):
            if memory_service is None:
                raise AssertionError("validated memory operation is missing its service")
            return asyncio.run(
                run_memory_command(
                    memory_service,
                    remember=args.remember,
                    kind=MemoryKind(args.memory_kind),
                    key=args.memory_key,
                    list_memory=args.list_memory,
                    inspect_id=args.inspect_memory,
                    forget_id=args.forget_memory,
                    json_mode=args.json,
                )
            )
        config = load_config(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            api_key_env=args.api_key_env,
            include_stream_usage=not args.no_stream_usage,
            fake_response=args.fake_response,
            fake_scenario=args.fake_scenario,
            context_window=args.context_window,
        )
        limits = RuntimeLimits(
            max_model_calls=args.max_model_calls,
            max_tool_rounds=args.max_tool_rounds,
            max_turn_seconds=args.timeout,
        )
    except (ConfigurationError, WorkspaceError, ValueError) as exc:
        return render_config_error(str(exc), json_mode=args.json)

    provider = _build_provider(config, resuming=args.resume is not None)
    if memory_service is not None and args.memory_writer == "llm":
        memory_service.writer = StructuredExtractionWriter(
            provider=provider,
            model=config.model,
        )
    renderer = NullEventSink() if args.json else PlainEventRenderer()
    application = build_application(
        provider=provider,
        model=config.model,
        workspace=workspace,
        tools=ToolRegistry(coding_tools()),
        limits=limits,
        event_sink=renderer,
        permission_mode=PermissionMode(args.permission_mode),
        session_store=session_store,
        context_window=config.context_window,
        memory_service=memory_service,
    )
    if args.resume is not None:
        return asyncio.run(
            _run_resume_command(
                application,
                args.resume,
                choice=args.permission_choice,
                json_mode=args.json,
            )
        )
    if args.prompt is not None:
        return asyncio.run(_run_one_shot(application, args.prompt, json_mode=args.json))

    console = Console()
    application.agent_loop.event_sink = RichEventRenderer(console)
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
        reader = _read_console_line if sys.stdin.isatty() else _read_redirected_line
        result = await resolve_waiting(
            application,
            result,
            json_mode=json_mode,
            read_line=reader,
        )
    finally:
        await application.aclose()
    return render_turn_result(result, json_mode=json_mode)


async def _run_resume_command(
    application: AgentApplication,
    session_id: str,
    *,
    choice: str | None,
    json_mode: bool,
) -> int:
    try:
        reader = _read_console_line if sys.stdin.isatty() else _read_redirected_line
        result = await resume_session(
            application,
            session_id,
            choice=choice,
            json_mode=json_mode,
            read_line=reader,
        )
    finally:
        await application.aclose()
    return render_turn_result(result, json_mode=json_mode)


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


def _build_provider(config: AppConfig, *, resuming: bool = False) -> ChatProvider:
    if config.provider == "fake":
        if resuming:
            return FakeProvider(script=(FakeResponse(text="持久化 Session 恢复完成。"),))
        if config.fake_scenario == "readonly":
            final_text = (
                "只读演示完成：Grep 定位到 src/coding_agent/protocol/models.py，"
                "Read 随后读取了该文件开头并确认 ProviderErrorKind 的定义。"
            )
            return FakeProvider(script=readonly_demo_script(final_text))
        if config.fake_scenario == "write":
            return FakeProvider(script=write_demo_script("写入与 PowerShell 验证演示完成。"))
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


def _render_session_list(store: JsonlSessionStore, *, json_mode: bool) -> int:
    try:
        sessions = session_summaries(store)
    except ValueError as exc:
        return render_config_error(str(exc), json_mode=json_mode)
    if json_mode:
        print(
            json.dumps(
                {"schema_version": 1, "sessions": sessions},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    else:
        for session in sessions:
            print(
                f"{session['session_id']}  {session['status']}  "
                f"messages={session['message_count']}  updated={session['updated_at']}"
            )
    return 0
