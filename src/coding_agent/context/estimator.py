"""Token 估算：本地字符近似，不绑定具体 tokenizer。

这是 FirstCoder FC:9.2 的翻译。刻意用「字符数÷4」近似，原因：
- context 层不该过早依赖具体 provider 的 tokenizer（我们支持 fake / openai-compatible
  等多个 provider，它们的 token 口径不完全一致）；
- 压缩触发只需相对量级（当前输入是否逼近水位），绝对值不精确也可用；
- 本地估算先行，实际 usage 仅事后校准（产品决策 #10），估算器是 Stage 4 压缩的判定原料。
"""

from __future__ import annotations

import json

from coding_agent.protocol import ToolDefinition
from coding_agent.session import AgentMessage, MessagePart, PartKind, SessionSnapshot


def estimate_text_tokens(text: str) -> int:
    """估算一段文本的 token 数：``max(1, (len + 3) // 4)``（字符数÷4 近似）。

    与 FC 的 ``estimate_text_tokens`` 完全一致。下限为 1，避免空文本贡献 0 token。
    """
    return max(1, (len(text) + 3) // 4)


def estimate_message_tokens(message: AgentMessage) -> int:
    """估算一条事实消息（AgentMessage）的投影 token 数。

    对每条消息，估算其会投影成 ModelMessage 后占据的 token：
    - user：文本 part 拼接后的字符数；
    - assistant：推理文本 + 正文文本 + 每个 tool_call 的 arguments_json；
    - tool：tool_result part 的内容。

    另加一个小的消息级固定开销（role 字段、消息包装，每消息 1 token），与 FC 的
    ``_estimate_chat_message_tokens`` 思路一致。
    """
    if message.role == "user":
        content_chars = sum(len(part.content) for part in message.parts if part.content is not None)
        return _chars_to_tokens(content_chars) + 1
    if message.role == "assistant":
        content_chars = 0
        for part in message.parts:
            if part.kind is PartKind.TOOL_CALL:
                content_chars += _tool_call_arguments_chars(part)
            elif part.content is not None:
                content_chars += len(part.content)
        return _chars_to_tokens(content_chars) + 1
    if message.role == "tool":
        content_chars = sum(
            len(part.content)
            for part in message.parts
            if part.kind is PartKind.TOOL_RESULT and part.content is not None
        )
        return _chars_to_tokens(content_chars) + 1
    raise ValueError(f"unknown fact message role: {message.role}")


def estimate_tool_definition_tokens(tool: ToolDefinition) -> int:
    """估算一个工具 schema 的 token 数。

    工具定义在请求中占据 ``name + description + input_schema``。schema 用紧凑 JSON
    序列化后按字符近似。下限为 1。
    """
    schema = json.dumps(tool.input_schema, ensure_ascii=False, separators=(",", ":"))
    total_chars = len(tool.name) + len(tool.description) + len(schema)
    return max(1, (total_chars + 3) // 4)


def estimate_snapshot_tokens(snapshot: SessionSnapshot, tools: tuple[ToolDefinition, ...]) -> int:
    """估算整个 SessionSnapshot + tools 的总 token（不含 system guidance）。"""
    history = sum(estimate_message_tokens(message) for message in snapshot.messages)
    tool_schema = sum(estimate_tool_definition_tokens(tool) for tool in tools)
    return history + tool_schema


def _chars_to_tokens(chars: int) -> int:
    return max(1, (chars + 3) // 4)


def _tool_call_arguments_chars(part: MessagePart) -> int:
    arguments = part.metadata.get("arguments_json")
    if isinstance(arguments, str):
        return len(arguments)
    return len(part.content or "")
