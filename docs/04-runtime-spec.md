# Agent Runtime 规范

## 1. AgentLoop 的职责

`AgentLoop` 是唯一正式模型—工具循环。它负责：

- 一轮任务的生命周期；
- 模型调用与工具调用的交替；
- 状态转换与运行时事件；
- 权限暂停和恢复；
- 调用次数、工具轮次、时间和取消限制；
- Provider 错误恢复；
- CompletionGate 调度。

它不负责：

- 厂商 HTTP 请求细节；
- 文件、Shell 的具体执行；
- Context 预算与压缩算法的具体实现；
- UI 渲染；
- 长期记忆检索规则。

## 2. 核心接口草案

```python
class ChatProvider(Protocol):
    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...

class Tool(Protocol):
    definition: ToolDefinition
    async def execute(self, arguments: dict[str, object], ctx: ToolContext) -> ToolResult: ...

class SessionStore(Protocol):
    def append(self, event: SessionEvent) -> None: ...
    def replay(self, session_id: str) -> SessionView: ...

class ContextEngine(Protocol):
    def build(self, view: SessionView, request: ContextRequest) -> ModelRequest: ...

class PermissionManager(Protocol):
    def decide(self, request: PermissionRequest) -> PermissionDecision: ...
```

M6 评审后可在 ContextEngine 内部引入 TokenEstimator 等接口；正式实现可调整次级命名，但边界不得被合并为一个万能 Agent 类。

## 3. 标准循环伪代码

```python
append(user_message)
state = PREPARING

while limits.allow_next_model_call():
    model_request = context_engine.build(session.replay())
    response = await provider.complete_or_stream(model_request)
    append(response_facts)

    if not response.tool_calls:
        verdict = completion_gate.evaluate(session.replay(), response.text)
        if verdict.can_finish:
            append(turn_finished(verdict.stop_reason))
            return TurnResult(response.text, verdict)
        append(message_added(role="runtime", content=verdict.feedback))
        continue

    for tool_call in tool_orchestrator.plan(response.tool_calls):
        outcome = await tool_orchestrator.execute_or_pause(tool_call)
        append(outcome.events)
        if outcome.requires_user:
            append(turn_finished("waiting_for_permission"))
            return TurnResult.waiting(outcome.request)

append(terminal_limited)
```

## 4. 最小事件模型

事件分成两个不同类型，避免在同一个 `RuntimeEvent` 上维护 `durable=True/False` 双重语义。

### Durable `SessionEvent`

P0 注册表限制为以下 11 个类型：

| 类型 | 关键 payload |
| --- | --- |
| `session_started` | workspace、配置摘要、已加载规则文件哈希 |
| `turn_started` | 输入模式、父 turn |
| `message_added` | role、完整 content、tool calls/results 或 runtime guidance |
| `provider_call_recorded` | status、model、attempt、usage、error；不重复保存完整消息 |
| `permission_requested` | request、原始本地 tool call 引用 |
| `permission_resolved` | decision、scope、用户反馈 |
| `tool_lifecycle` | tool call、`requested/started/completed/failed/cancelled/uncertain` 状态和结果 |
| `todo_updated` | revision、完整当前计划 |
| `artifact_created` | 路径、哈希、大小、来源 |
| `context_checkpoint_committed` | 覆盖事件范围、摘要和估算 Token |
| `turn_finished` | status、stop_reason、completion/verification 摘要 |

不同生命周期阶段放在 payload 的枚举字段中，不为每个阶段扩张新的事件类型。只有重放、审计或恢复需要的事实才进入 JSONL。

### Ephemeral `UiEvent`

P0 只需要 `model_text_delta`、`activity_changed` 和 `diff_ready`。它们可投影到 CLI/Trace，但不写 Session JSONL，也不能参与恢复。模型完整文本与终态仍通过 durable 事件保存。

## 5. 停止条件

一轮任务至少同时受以下限制：

- `max_model_calls`
- `max_tool_rounds`
- `max_turn_seconds`
- `max_total_tokens`
- cancellation token

停止原因必须是枚举值，不得统一返回“无法完成”：

- `completed`
- `completed_unverified`
- `waiting_for_permission`
- `cancelled`
- `model_call_limit`
- `tool_round_limit`
- `turn_timeout`
- `token_budget_exceeded`
- `provider_error`
- `internal_error`

### CompletionGate 规则

CompletionGate 是确定性程序检查，不使用第二次 LLM 判断：

- 存在未结算 tool call 或 pending permission：不得完成。
- 存在 `pending`/`in_progress` Todo：不得完成，并反馈具体条目。
- 最近一次成功文件修改之后没有验证证据：至少阻止一次完成，把“有 N 个文件未验证”作为 runtime guidance 交回模型。
- 验证证据必须来自修改后的 `Shell` 结果或明确的静态检查记录；模型文字不算证据。
- Gate 最多进行两轮补救反馈，防止无限循环。
- 仅当用户明确要求跳过验证、验证命令客观不可用，或两轮补救已耗尽时，才允许 `completed_unverified`；结果必须列出缺失证据/阻塞原因，不得声称“全部验证通过”。

没有文件修改的解释类任务，`verified` 为 `null`，不因缺少测试而降级。

## 6. Provider 错误恢复

| 错误 | 默认策略 |
| --- | --- |
| timeout/network | 有界指数退避，最多重试两次 |
| rate_limit | 尊重 retry-after，否则有界退避 |
| prompt_too_long | 触发一次强制压缩并重建请求 |
| malformed_tool_arguments | 返回结构化工具错误，让模型最多修正一次 |
| auth/config | 立即失败，不重试 |
| content_filter | 明确终止 |
| truncated_tool_call | 丢弃未完整调用，不执行 |

## 7. 权限暂停与恢复

暂停时持久化：

- `request_id`
- 本地原始 `tool_call_id` 和工具参数摘要
- 权限问题与可选项
- 进入暂停前的状态

可执行工具参数保存在本地可信状态。用户回答只表达允许范围或拒绝反馈，不能替换原始工具调用。

暂停的语义是“持久化后 return”，不是在内存中跨 `await` 悬挂 AgentLoop：

- AgentLoop 不跨等待用户、进程退出或 CLI 重启保留可变调用栈。
- resume 先由 SessionStore 重放为 SessionView，再通过与新会话相同的 composition path 进入 AgentLoop。
- 恢复只消费 Event Log 中的 pending request 和原始 tool call；内存中恰好仍存在的对象不具备额外权威。

## 8. 并发规则

P0 全部串行，优先保证事件顺序可解释。

P2 只允许被 Tool 声明为 `read_only=True` 且 `concurrency_safe=True` 的调用并发。同一个模型响应中的写入、Shell 和未知工具始终串行。结果按原始 tool call 顺序写回模型视图。

## 9. TodoWrite 状态机（M7 实现契约）

Todo 不是每个简单任务的必需品。模型选择使用后，必须遵循：

```text
Plan = { revision: int, items: [{ id, text, status, blocked_reason? }] }
status = pending | in_progress | completed | blocked
```

- 更新必须携带 `expected_revision`；不匹配返回 `revision_conflict`。
- 同一计划最多一个 `in_progress`。
- 合法转换：`pending -> in_progress|blocked`，`in_progress -> completed|blocked|pending`，`blocked -> pending|in_progress`。
- `completed` 默认是终态；重新打开必须显式携带原因并产生新 revision。
- `blocked` 必须有 `blocked_reason`；它不等于已完成，但可让 CompletionGate 产生带阻塞说明的 `completed_unverified`。
- Todo 状态不根据模型最终文本自动修改，也不替代真实验证证据。
