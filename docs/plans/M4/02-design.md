# M4 设计

## 工具执行管线

```text
ToolCall
  -> ToolRegistry.prepare（JSON/Schema/Workspace/预览）
  -> PermissionManager.preflight
  -> ALLOW: execute_prepared
  -> DENY: permission_denied ToolResult
  -> ASK: 保存 PendingPermissionExecution 并返回 Application
  -> CLI 展示可信 request/diff
  -> Application.resume_permission
  -> PermissionManager.resolve
  -> Edit 快照复查
  -> execute_prepared 或 stale_snapshot
  -> ToolResult 配对写回 Session
  -> AgentLoop 继续
```

Tool 可声明权限请求和 prepared payload，但不能决定 allow/ask/deny。

## Edit

单一模型可见工具支持 `create`、`replace`、`delete`。replace 要求 old_text 唯一匹配，除非显式
`replace_all=true`。Preview 保存 before digest、候选内容、Diff 和行统计；用户回传只包含 request
ID 与选择，不回传 ToolCall 或候选内容。

写入使用同目录临时文件、flush/fsync 和 `os.replace`；已有文件尽量保留 mode。删除只支持文件，
不递归删除目录。

## Permission

- plan：副作用 DENY。
- standard：Edit/Shell ASK。
- bypass：副作用 ALLOW。
- allow_session 仅生成当前进程、当前 Application 内的 Edit exact-path grant。
- deny 和硬策略优先于 grant；Shell 永不创建 grant。

## 暂停与继续

M4 PendingPermissionExecution 保存在 AgentLoop 的进程内可信状态，包含原 ToolCall、prepared
payload、PermissionRequest、同响应剩余调用和 Turn 计数。等待用户时 AgentLoop return；resume
从 pending 对象继续，不接受 CLI 重构工具参数。M5 将同一语义迁到 durable SessionEvent。

## Shell

PowerShell 使用参数数组启动，不通过额外 shell 拼接。cwd 由 Workspace 解析；timeout/cancel 时
终止进程树。结果包含 command、cwd、exit_code、stdout/stderr 和截断状态。命令检查只用于确认
界面解释，不改变 ASK。

## TodoWrite

M4 保存完整 Todo 快照并执行基本 revision/状态约束；M7 再接 CompletionGate 和完成证据。
