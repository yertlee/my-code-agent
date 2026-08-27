from __future__ import annotations

import json
import sys
from typing import Any

from coding_agent.protocol import ErrorInfo, TokenUsage, TurnResult, TurnStatus


def render_turn_result(result: TurnResult, *, json_mode: bool) -> int:
    if json_mode:
        print(json.dumps(result.to_dict(), ensure_ascii=False, separators=(",", ":")))
    else:
        if result.output_text:
            print()
        if result.error is not None:
            print(
                f"provider error [{result.error.kind}]: {result.error.message}",
                file=sys.stderr,
            )
        elif result.status is not TurnStatus.COMPLETED:
            print(f"agent stopped [{result.stop_reason}]", file=sys.stderr)
    return exit_code(result)


def render_config_error(message: str, *, json_mode: bool) -> int:
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


def configure_utf8_stdio() -> None:
    """Keep redirected Windows output and JSON consistently UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure: Any | None = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def exit_code(result: TurnResult) -> int:
    if result.status is TurnStatus.COMPLETED:
        return 0
    if result.status in {TurnStatus.LIMITED, TurnStatus.CANCELLED}:
        return 4
    if result.status is TurnStatus.WAITING:
        return 3
    return 1
