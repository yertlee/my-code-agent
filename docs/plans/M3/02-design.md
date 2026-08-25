# M3 设计

## 唯一装配路径

```text
CLI
  -> build_application
  -> AgentApplication
  -> AgentLoop
  -> InMemorySessionStore
  -> BasicContextBuilder + EmptyMemoryRetriever
  -> ChatProvider
  -> ReadOnlyPermissionPolicy
  -> ToolRegistry + Workspace
```

one-shot 和交互式入口只在输入、活动渲染和进程退出方式上不同，不分别组装 AgentLoop。

## 模块职责

- `app`：composition root、Application 生命周期与当前 Session。
- `agent`：唯一模型—工具循环、限制、错误和 TurnResult。
- `runtime`：RuntimeEvent、CancellationToken 和用户输入端口。
- `session`：M3 内存事实与 SessionSnapshot。
- `context`：从 SessionSnapshot、MemoryProjection 和 ToolDefinition 构造 ModelRequest。
- `memory`：M3 返回空投影，但调用边界真实存在。
- `permissions`：在 ToolRegistry 前做只读 allow/deny。

## Session 语义

Application 第一次运行任务时创建 Session；交互式后续任务复用它。每个 Turn 使用新 turn_id，
消息、Usage 和工具历史保留在 Session 内存中。one-shot 运行结束后 Application 关闭，因此不会
产生跨进程持久化承诺。

## Provider 生命周期

AgentLoop 不拥有 Provider 关闭职责。`AgentApplication.aclose()` 关闭 Provider；CLI 必须在
one-shot、交互式正常退出、配置后运行失败和 KeyboardInterrupt 路径执行关闭。

## RuntimeEvent

M3 使用少量展示活动：

- `turn_started`
- `text_delta`
- `tool_started`
- `tool_completed`
- `turn_finished`

活动携带 session_id、turn_id 和必要 payload，不作为 Session 持久化事实，也不参与恢复。

## 权限边界

ReadOnlyPermissionPolicy 根据 ToolDefinition/工具名判定。M3 允许 Read、Glob、Grep；其他工具
返回 denied ToolResult。M4 再增加 ask、grant、模式与用户确认。

## 兼容策略

- `app.run_prompt` 保留为薄兼容函数，内部创建并关闭 AgentApplication。
- CLI flags、TurnResult schema v1、Provider-neutral DTO 和只读工具参数保持不变。
- 测试迁移到 AgentLoop/Application 公共入口，不保留第二个循环实现。
