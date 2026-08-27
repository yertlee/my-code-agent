"""AgentLoop 的纯辅助结构与函数（无 loop 实例状态）。

从 ``loop.py`` 拆出以维持「AgentLoop ≤ 500 行」的 kernel 预算。这些 dataclass /
纯函数只做数据转换，不依赖 AgentLoop 实例状态，``loop.py`` 从本模块导入。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256

from coding_agent.permissions import PermissionAction, PermissionRequest
from coding_agent.protocol import PendingInputInfo, TokenUsage
from coding_agent.session import PendingPermission, SessionSnapshot, TurnIdentity
from coding_agent.tools.base import PreparedToolCall


@dataclass(slots=True)
class TurnState:
    identity: TurnIdentity
    tools_used: list[str] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    model_calls: int = 0
    tool_rounds: int = 0
    last_output_text: str = ""
    memory_considered: int = 0
    memory_recalled_ids: list[str] = field(default_factory=list)
    memory_written_ids: list[str] = field(default_factory=list)


def add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    def merge(a: int | None, b: int | None) -> int | None:
        if a is None and b is None:
            return None
        return (a or 0) + (b or 0)

    return TokenUsage(
        input_tokens=merge(left.input_tokens, right.input_tokens),
        output_tokens=merge(left.output_tokens, right.output_tokens),
        total_tokens=merge(left.total_tokens, right.total_tokens),
    )


def state_from_pending(pending: PendingPermission) -> TurnState:
    return TurnState(
        identity=pending.identity,
        tools_used=list(pending.tools_used),
        usage=pending.usage,
        model_calls=pending.model_calls,
        tool_rounds=pending.tool_rounds,
        last_output_text=pending.last_output_text,
    )


def pending_input(
    request: PermissionRequest,
    preview: dict[str, object] | None,
    options: tuple[str, ...] | None = None,
) -> PendingInputInfo:
    display_target = str(request.metadata.get("path") or request.target)
    if options is None:
        values = ["deny", "allow_once"]
        if request.action in {PermissionAction.WRITE, PermissionAction.DELETE}:
            values.append("allow_session")
        options = tuple(values)
    return PendingInputInfo(
        request_id=request.request_id,
        kind="permission_confirmation",
        question=f"Allow {request.action.value}: {display_target}?",
        options=options,
        payload={
            "action": request.action.value,
            "target": display_target,
            "reason": request.reason,
            "preview": preview,
        },
    )


def confirmation_matches(pending: PendingPermission, prepared: PreparedToolCall) -> bool:
    return pending.confirmation_fingerprint == confirmation_fingerprint(
        prepared.preflight.permission_request,
        prepared.preflight.preview,
    )


def confirmation_fingerprint(
    request: PermissionRequest,
    preview: dict[str, object] | None,
) -> str:
    payload = {
        "action": request.action.value,
        "target": request.target,
        "reason": request.reason,
        "metadata": request.metadata,
        "preview": preview,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return sha256(encoded.encode("utf-8")).hexdigest()


def latest_user_text(snapshot: SessionSnapshot, turn_id: str) -> str:
    for message in reversed(snapshot.messages):
        if message.turn_id == turn_id and message.role == "user":
            return "".join(part.content or "" for part in message.parts)
    return ""


def memory_summary(state: TurnState, *, enabled: bool) -> dict[str, object] | None:
    if not enabled:
        return None
    return {
        "considered": state.memory_considered,
        "recalled": len(state.memory_recalled_ids),
        "recalled_ids": state.memory_recalled_ids,
        "written": len(state.memory_written_ids),
        "written_ids": state.memory_written_ids,
    }
