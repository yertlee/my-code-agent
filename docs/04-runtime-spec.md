# Agent Kernel Runtime

## 1. AgentLoop 职责

`AgentLoop` 是唯一模型—工具驱动，负责：

- 开始一轮 Turn；
- 通过 ContextBuilder 构造请求；
- 消费 ChatProvider stream；
- 串行处理 Tool Call；
- 调用 PermissionManager；
- 在权限等待时返回 TurnResult；
- 执行模型调用、工具轮次、时间和取消限制；
- 产生 RuntimeEvent 与最终 TurnResult。

Provider HTTP、文件实现、命令进程、CLI 渲染和未来 Session/Context/Memory 算法属于能力扩展。

## 2. Kernel contracts

```python
class ChatProvider(Protocol):
    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]: ...

class ContextBuilder(Protocol):
    def build(self, *, model, snapshot, tools) -> ModelRequest: ...

class SessionStore(Protocol):
    def begin_turn(self, prompt, *, session_id=None) -> TurnIdentity: ...
    def append_message(self, session_id, message) -> None: ...
    def add_usage(self, session_id, usage) -> None: ...
    def snapshot(self, session_id) -> SessionSnapshot: ...

class Tool(Protocol):
    definition: ToolDefinition
    async def execute(self, arguments, context) -> ToolExecution: ...

class EventSink(Protocol):
    def emit(self, event: RuntimeEvent) -> None: ...
```

PermissionPolicy 是 PermissionManager 内的策略 seam；ToolRegistry 是 AgentLoop 依赖的稳定 Tool host。

## 3. 当前循环

```text
begin_turn(user prompt)
while model_calls < limit:
  request = context_builder.build(session.snapshot(), tools)
  response = provider.stream(request)

  if response has no tool calls:
    append assistant message
    return completed

  append assistant tool-call message
  for call in response.tool_calls:
    prepared = tool_registry.prepare(call)
    decision = permission_manager.preflight(prepared.request)

    if decision is ASK:
      keep trusted prepared call in current AgentLoop
      return waiting
    if decision is DENY:
      append permission_denied ToolResult
      continue

    execute_prepared()
    append ToolResult

return limited
```

M5 将把进程内 pending 状态替换为 SessionStore 可恢复事实，但仍通过该循环继续，不创建恢复专用
Agent Loop。

## 4. TurnResult

当前状态：

- `completed`
- `waiting`
- `limited`
- `cancelled`
- `failed`

当前停止原因：

- `completed`
- `waiting_for_permission`
- `model_call_limit`
- `tool_round_limit`
- `turn_timeout`
- `cancelled`
- `provider_error`
- `incomplete_provider_stream`

新增状态和停止原因必须在同一里程碑拥有 producer、CLI renderer 和测试。

## 5. Ephemeral RuntimeEvent

当前事件注册表：

- `turn_started`
- `text_delta`
- `tool_started`
- `tool_completed`
- `diff_ready`
- `permission_requested`
- `permission_resolved`
- `turn_finished`

它们用于 CLI/测试观察，不是持久化 Session 事实。M5 的 durable events 使用独立模型，并受最多 7
类事件的里程碑预算约束。

## 6. 权限暂停

M4 的 pending prepared call 存在于当前 AgentLoop：

- CLI 只收到 request ID、问题、选项和可信 preview；
- CLI 只返回 request ID 与 choice；
- AgentLoop 使用原始 prepared call 执行；
- Edit 执行前重新检查 snapshot。

该协议是 M5 跨进程恢复的用户行为基线。

## 7. 限制与取消

- 默认最多 8 次模型调用；
- 默认最多 6 个工具轮次；
- 默认 Turn 总时限 120 秒；
- CancellationToken 在 Provider stream 和 Tool 边界协作检查；
- Shell 自己负责命令 timeout 和取消后的进程清理。
