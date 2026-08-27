"""Session 事实层核心模型：AgentMessage / MessagePart。

这是 FirstCoder 风格的事实账本：只描述「真实发生过」的消息、工具调用、工具结果与
权限状态，与 provider 请求格式（ModelMessage）严格分离。Context projection 每次
请求再从事实投影回 ModelMessage，压缩/裁剪只影响投影视图，绝不篡改事实。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from coding_agent.protocol import ToolCall, ToolResult


class PartKind(StrEnum):
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


def utc_now_iso() -> str:
    """稳定的 UTC ISO 时间（微秒置 0，Z 后缀）。"""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_message_id() -> str:
    """生成稳定消息事实 id（uuid4 hex）。"""
    return f"msg_{uuid4().hex}"


def new_part_id() -> str:
    """生成稳定消息部件 id（uuid4 hex）。"""
    return f"part_{uuid4().hex}"


@dataclass(frozen=True, slots=True)
class MessagePart:
    """一条 AgentMessage 的组成部分：文本 / 工具调用 / 工具结果。"""

    id: str
    message_id: str
    kind: PartKind
    content: str | None
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "message_id": self.message_id,
            "kind": self.kind.value,
            "content": self.content,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> MessagePart:
        return cls(
            id=_required_str(value, "id"),
            message_id=_required_str(value, "message_id"),
            kind=PartKind(_required_str(value, "kind")),
            content=None if value.get("content") is None else str(value["content"]),
            metadata=_object_dict(value.get("metadata")),
        )


@dataclass(frozen=True, slots=True)
class AgentMessage:
    """一条不可变会话事实消息（role 为 user / assistant / tool）。"""

    id: str
    session_id: str
    turn_id: str
    role: str
    parts: tuple[MessagePart, ...]
    created_at: str
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "role": self.role,
            "parts": [part.to_dict() for part in self.parts],
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> AgentMessage:
        parts_value = value.get("parts")
        if not isinstance(parts_value, list):
            raise ValueError("parts must be an array")
        return cls(
            id=_required_str(value, "id"),
            session_id=_required_str(value, "session_id"),
            turn_id=_required_str(value, "turn_id"),
            role=_required_str(value, "role"),
            parts=tuple(MessagePart.from_dict(_part_dict(part)) for part in parts_value),
            created_at=_required_str(value, "created_at"),
            metadata=_object_dict(value.get("metadata")),
        )


def user_message(
    session_id: str,
    content: str,
    *,
    turn_id: str,
    message_id: str | None = None,
) -> AgentMessage:
    """构造一条 user 事实消息（文本 part 承载用户输入）。"""
    message_id = message_id or new_message_id()
    part = MessagePart(
        id=new_part_id(),
        message_id=message_id,
        kind=PartKind.TEXT,
        content=content,
    )
    return AgentMessage(
        id=message_id,
        session_id=session_id,
        turn_id=turn_id,
        role="user",
        parts=(part,),
        created_at=utc_now_iso(),
    )


def assistant_message(
    session_id: str,
    *,
    turn_id: str,
    text: str | None,
    tool_calls: tuple[ToolCall, ...] = (),
    reasoning_content: str | None = None,
    message_id: str | None = None,
) -> AgentMessage:
    """构造一条 assistant 事实消息。

    - 推理内容以带 ``reasoning`` 标记的 text part 保存；
    - 正文以普通 text part 保存；
    - 每个工具调用以 tool_call part 保存（metadata 携带调用三要素）。
    """
    message_id = message_id or new_message_id()
    parts: list[MessagePart] = []
    if reasoning_content:
        parts.append(
            MessagePart(
                id=new_part_id(),
                message_id=message_id,
                kind=PartKind.TEXT,
                content=reasoning_content,
                metadata={"reasoning": True},
            )
        )
    if text:
        parts.append(
            MessagePart(
                id=new_part_id(),
                message_id=message_id,
                kind=PartKind.TEXT,
                content=text,
            )
        )
    for call in tool_calls:
        parts.append(
            MessagePart(
                id=new_part_id(),
                message_id=message_id,
                kind=PartKind.TOOL_CALL,
                content=None,
                metadata={
                    "tool_call_id": call.id,
                    "tool_name": call.name,
                    "arguments_json": call.arguments_json,
                },
            )
        )
    return AgentMessage(
        id=message_id,
        session_id=session_id,
        turn_id=turn_id,
        role="assistant",
        parts=tuple(parts),
        created_at=utc_now_iso(),
    )


def tool_result_message(
    session_id: str,
    result: ToolResult,
    *,
    turn_id: str,
) -> AgentMessage:
    """把一条 ToolResult 落成 tool 事实消息（tool_result part）。

    metadata 携带 lifecycle 分类所需的原料：tool_call_id / tool_name / ok / truncated，
    并合并 ToolResult 自带的 metadata（如 read 的 path/start_line、shell 的 exit_code）。
    """
    message_id = new_message_id()
    metadata = {
        **result.metadata,
        "tool_call_id": result.tool_call_id,
        "tool_name": result.tool_name,
        "ok": not result.is_error,
        "truncated": result.truncated,
    }
    part = MessagePart(
        id=new_part_id(),
        message_id=message_id,
        kind=PartKind.TOOL_RESULT,
        content=result.content,
        metadata=metadata,
    )
    return AgentMessage(
        id=message_id,
        session_id=session_id,
        turn_id=turn_id,
        role="tool",
        parts=(part,),
        created_at=utc_now_iso(),
    )


def _required_str(value: dict[str, object], field_name: str) -> str:
    raw = value.get(field_name)
    if raw is None or not isinstance(raw, str):
        raise ValueError(f"{field_name} must be a string")
    return raw


def _part_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("part must be an object")
    return value


def _object_dict(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError("metadata must be an object")
    return value
