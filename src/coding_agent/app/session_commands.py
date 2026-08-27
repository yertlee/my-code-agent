from __future__ import annotations

import sys

from coding_agent.app.application import AgentApplication
from coding_agent.app.interactive import ReadLine
from coding_agent.protocol import ErrorInfo, TokenUsage, TurnResult, TurnStatus
from coding_agent.session import JsonlSessionStore, SessionError


def validate_session_options(
    *,
    prompt: str | None,
    resume: str | None,
    list_sessions: bool,
    json_mode: bool,
    permission_choice: str | None,
    session_dir: str | None,
    remember: str | None,
    list_memory: bool,
    inspect_memory: str | None,
    forget_memory: str | None,
    memory_dir: str | None,
    memory_key: str | None,
) -> str | None:
    selected = sum(
        value is not None or enabled
        for value, enabled in (
            (prompt, False),
            (resume, False),
            (None, list_sessions),
            (remember, False),
            (None, list_memory),
            (inspect_memory, False),
            (forget_memory, False),
        )
    )
    if selected > 1:
        return "choose exactly one CLI operation"
    if json_mode and selected == 0:
        return "--json requires one CLI operation"
    if (resume is not None or list_sessions) and session_dir is None:
        return "--resume and --list-sessions require --session-dir"
    memory_operation = any(
        (remember is not None, list_memory, inspect_memory is not None, forget_memory is not None)
    )
    if memory_operation and memory_dir is None:
        return "memory operations require --memory-dir"
    if memory_key is not None and remember is None:
        return "--memory-key requires --remember"
    if permission_choice is not None and resume is None:
        return "--permission-choice requires --resume"
    if json_mode and resume is not None and permission_choice is None:
        return "JSON resume requires --permission-choice"
    return None


async def resume_session(
    application: AgentApplication,
    session_id: str,
    *,
    choice: str | None,
    json_mode: bool,
    read_line: ReadLine,
) -> TurnResult:
    try:
        pending = application.pending_permission(session_id)
        if pending is None:
            raise SessionError("no_pending_permission", f"session is not waiting: {session_id}")
        if choice is None:
            _show_pending(pending.question, pending.options)
            choice = await read_line("permission> ")
        result = await application.resume_permission(pending.request_id, choice)
        return await resolve_waiting(
            application,
            result,
            json_mode=json_mode,
            read_line=read_line,
        )
    except SessionError as exc:
        return _session_error_result(session_id, exc)


async def resolve_waiting(
    application: AgentApplication,
    result: TurnResult,
    *,
    json_mode: bool,
    read_line: ReadLine,
) -> TurnResult:
    if json_mode:
        return result
    while result.status is TurnStatus.WAITING and result.pending_input is not None:
        pending = result.pending_input
        _show_pending(pending.question, pending.options)
        try:
            answer = await read_line("permission> ")
        except (EOFError, KeyboardInterrupt):
            break
        result = await application.resume_permission(pending.request_id, answer)
    return result


def session_summaries(store: JsonlSessionStore) -> tuple[dict[str, object], ...]:
    return store.list_sessions()


def _show_pending(question: str, options: tuple[str, ...]) -> None:
    print(question, file=sys.stderr)
    print("options: " + ", ".join(options), file=sys.stderr)


def _session_error_result(session_id: str, error: SessionError) -> TurnResult:
    return TurnResult(
        schema_version=1,
        session_id=session_id,
        turn_id="",
        status=TurnStatus.FAILED,
        stop_reason="session_error",
        output_text="",
        verified=None,
        verification=(),
        tools_used=(),
        usage=TokenUsage(),
        error=ErrorInfo(error.code, str(error), False),
    )
