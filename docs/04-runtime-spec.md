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

Provider HTTP、文件实现、命令进程、CLI 渲染和 Session/Context/Memory 策略属于能力扩展。

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

class PendingPermissionStore(Protocol):
    def save_pending(self, pending) -> None: ...
    def pending_for_session(self, session_id) -> PendingPermission | None: ...
    def claim_pending(self, request_id, choice) -> PendingPermission: ...

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
      save PendingPermission
      return waiting
    if decision is DENY:
      append permission_denied ToolResult
      continue

    execute_prepared()
    append ToolResult

return limited
```

resume 时，AgentLoop claim PendingPermission、重新 prepare 并校验确认 fingerprint，然后从同一循环
继续执行。

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

它们用于 CLI/测试观察，不是持久化 Session 事实。durable Session 使用 5 类独立 SessionEvent：
turn_started、message_appended、usage_added、permission_pending、permission_claimed。

## 6. 权限暂停

PendingPermission 是 SessionBackend 中的可恢复事实：

- CLI 只收到 request ID、问题、选项和可信 preview；
- CLI 只返回 request ID 与 choice；
- resume 先持久化 claim，再重新 prepare 原始 ToolCall；
- confirmation fingerprint 匹配后使用新生成的可信 opaque plan 执行；
- Edit 执行前继续检查 snapshot。

该协议同时用于进程内确认与 JSONL 跨进程恢复。

## 7. 限制与取消

- 默认最多 8 次模型调用；
- 默认最多 6 个工具轮次；
- 默认 Turn 总时限 120 秒；
- CancellationToken 在 Provider stream 和 Tool 边界协作检查；
- Shell 自己负责命令 timeout 和取消后的进程清理。
