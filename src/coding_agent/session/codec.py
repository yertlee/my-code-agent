from __future__ import annotations

from dataclasses import asdict

from coding_agent.permissions import PermissionAction, PermissionRequest
from coding_agent.protocol import ModelMessage, TokenUsage, ToolCall
from coding_agent.session.models import PendingPermission, TurnIdentity


def pending_to_dict(pending: PendingPermission) -> dict[str, object]:
    return asdict(pending)


def pending_from(value: dict[str, object]) -> PendingPermission:
    identity = object_value(value["identity"], "identity")
    request = object_value(value["request"], "request")
    preview_value = value.get("preview")
    return PendingPermission(
        identity=TurnIdentity(str(identity["session_id"]), str(identity["turn_id"])),
        call=tool_call_from(object_value(value["call"], "call")),
        remaining_calls=tuple(
            tool_call_from(object_value(item, "remaining_call"))
            for item in array_value(value["remaining_calls"], "remaining_calls")
        ),
        request=PermissionRequest(
            request_id=str(request["request_id"]),
            action=PermissionAction(str(request["action"])),
            target=str(request["target"]),
            reason=str(request["reason"]),
            metadata=object_value(request.get("metadata", {}), "metadata"),
        ),
        preview=(
            None if preview_value is None else object_value(preview_value, "preview")
        ),
        confirmation_fingerprint=str(value["confirmation_fingerprint"]),
        tools_used=tuple(
            str(item) for item in array_value(value["tools_used"], "tools_used")
        ),
        usage=usage_from(object_value(value["usage"], "usage")),
        model_calls=required_int(value["model_calls"], "model_calls"),
        tool_rounds=required_int(value["tool_rounds"], "tool_rounds"),
        last_output_text=str(value["last_output_text"]),
    )


def message_from(value: dict[str, object]) -> ModelMessage:
    return ModelMessage(
        role=str(value["role"]),
        content=None if value.get("content") is None else str(value["content"]),
        tool_calls=tuple(
            tool_call_from(object_value(item, "tool_call"))
            for item in array_value(value.get("tool_calls", []), "tool_calls")
        ),
        tool_call_id=(
            None if value.get("tool_call_id") is None else str(value["tool_call_id"])
        ),
        reasoning_content=(
            None
            if value.get("reasoning_content") is None
            else str(value["reasoning_content"])
        ),
    )


def tool_call_from(value: dict[str, object]) -> ToolCall:
    return ToolCall(str(value["id"]), str(value["name"]), str(value["arguments_json"]))


def usage_from(value: dict[str, object]) -> TokenUsage:
    return TokenUsage(
        optional_int(value.get("input_tokens")),
        optional_int(value.get("output_tokens")),
        optional_int(value.get("total_tokens")),
    )


def object_value(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field_name} must be an object")
    return value


def array_value(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array")
    return value


def optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("token usage must be an integer or null")
    return value


def required_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value
