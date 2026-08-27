from __future__ import annotations

from coding_agent.context import facts_to_model_messages
from coding_agent.protocol import ModelMessage, TokenUsage, ToolCall, ToolResult
from coding_agent.session import (
    AgentMessage,
    MessagePart,
    PartKind,
    SessionSnapshot,
    assistant_message,
    tool_result_message,
    user_message,
)


def test_message_part_round_trips_through_dict() -> None:
    part = MessagePart(
        id="part_1",
        message_id="msg_1",
        kind=PartKind.TOOL_CALL,
        content=None,
        metadata={"tool_call_id": "call_1", "tool_name": "Read", "arguments_json": "{}"},
    )

    restored = MessagePart.from_dict(part.to_dict())

    assert restored == part


def test_agent_message_round_trips_through_dict() -> None:
    call = ToolCall("call_1", "Grep", '{"query":"Target"}')
    message = assistant_message("ses_1", turn_id="turn_1", text="searching", tool_calls=(call,))

    restored = AgentMessage.from_dict(message.to_dict())

    assert restored == message
    assert restored.id == message.id
    assert restored.session_id == "ses_1"
    assert restored.role == "assistant"
    assert len(restored.parts) == 2
    assert restored.parts[0].kind is PartKind.TEXT
    assert restored.parts[0].content == "searching"
    assert restored.parts[1].kind is PartKind.TOOL_CALL
    assert restored.parts[1].metadata["tool_name"] == "Grep"
    assert restored.parts[1].metadata["tool_call_id"] == "call_1"


def test_tool_result_message_carries_lifecycle_metadata() -> None:
    result = ToolResult(
        tool_call_id="call_read",
        tool_name="Read",
        content="path: demo.py\n1: class Target:",
        metadata={"path": "demo.py", "start_line": 1, "end_line": 1},
    )

    message = tool_result_message("ses_1", result, turn_id="turn_1")

    assert message.role == "tool"
    part = message.parts[0]
    assert part.kind is PartKind.TOOL_RESULT
    assert part.content == result.content
    assert part.metadata["tool_call_id"] == "call_read"
    assert part.metadata["tool_name"] == "Read"
    assert part.metadata["ok"] is True
    assert part.metadata["truncated"] is False
    assert part.metadata["path"] == "demo.py"
    assert part.metadata["start_line"] == 1
    assert AgentMessage.from_dict(message.to_dict()) == message


def test_facts_projection_covers_user_assistant_tool() -> None:
    call = ToolCall("call_1", "Edit", '{"operation":"replace","path":"demo.py"}')
    result = ToolResult(
        tool_call_id="call_1",
        tool_name="Edit",
        content="replace completed: demo.py",
        is_error=False,
    )
    snapshot = SessionSnapshot(
        session_id="ses_1",
        messages=(
            user_message("ses_1", "change it", turn_id="turn_1"),
            assistant_message("ses_1", turn_id="turn_1", text=None, tool_calls=(call,)),
            tool_result_message("ses_1", result, turn_id="turn_1"),
            assistant_message("ses_1", turn_id="turn_1", text="done"),
        ),
        usage=TokenUsage(),
    )

    projected = facts_to_model_messages(snapshot)

    assert projected == (
        ModelMessage(role="user", content="change it"),
        ModelMessage(
            role="assistant",
            content=None,
            tool_calls=(call,),
        ),
        ModelMessage(role="tool", content="replace completed: demo.py", tool_call_id="call_1"),
        ModelMessage(role="assistant", content="done"),
    )


def test_facts_projection_joins_text_parts_and_reasoning() -> None:
    message = assistant_message(
        "ses_1",
        turn_id="turn_1",
        text="answer",
        reasoning_content="think first",
    )
    snapshot = SessionSnapshot(
        session_id="ses_1",
        messages=(user_message("ses_1", "q", turn_id="turn_1"), message),
        usage=TokenUsage(),
    )

    projected = facts_to_model_messages(snapshot)

    assert projected[0] == ModelMessage(role="user", content="q")
    assert projected[1] == ModelMessage(
        role="assistant",
        content="answer",
        reasoning_content="think first",
    )
