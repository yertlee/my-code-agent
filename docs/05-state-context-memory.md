# Session、Context 与 Memory

## 1. 三个系统的职责

| 系统 | 回答的问题 | 生命周期 | 核心输出 |
| --- | --- | --- | --- |
| Session | 实际发生了什么？ | 单个或多个连续 Turn | 可重放事实与 SessionView |
| Context | 下一次模型需要看到什么？ | 每次 Provider 请求 | 受预算约束的 ModelRequest |
| Memory | 未来任务值得复用什么？ | 跨 Session | 有来源和作用域的长期知识 |

三者拥有不同的数据和生命周期：

- Session 保存消息、工具、权限、任务状态、压缩活动和终态事实。
- Context 从 SessionView、项目规则、工具、当前任务和 Memory 构造模型视图。
- Memory 保存经过用户控制和来源校验的跨会话知识。

## 2. 共同不变量

- Session Event Log 是 Session 恢复所需的事实源。
- Context 压缩不能删除或改写 Session 原始事实。
- Memory 不能代替 Session 历史或恢复未完成工具。
- Context 和 Memory 必须保留来源关系。
- 当前仓库与工具证据优先于模型陈述和陈旧知识。
- 项目规则、Context 和 Memory 都不能提高工具权限。

## 3. Session

### 3.1 持久化

Session 使用 append-only JSONL：

```text
<workspace>/.coding-agent/
  sessions/<session-id>.jsonl
  artifacts/<session-id>/...
  permissions.json
  memory/...
```

每个事件至少包含 schema version、event/session/turn ID、严格递增 sequence、timestamp、类型
和 versioned payload。

### 3.2 SessionView

统一 Reducer 从事件回放得到：

- 有效消息；
- Tool Call、ToolResult 与生命周期；
- pending permission/user input；
- Todo；
- Context 状态引用；
- Usage；
- terminal state。

CLI、resume、ContextBuilder 和导出功能使用同一 SessionView。

### 3.3 恢复

- requested 但未 started：恢复为待处理，不自动执行。
- started 但没有终态：追加 uncertain，不自动重放。
- completed/failed/denied：恢复事实和结果，不再次执行。
- 权限等待：使用本地保存的原始 Tool Call 重建请求。
- JSONL 尾部损坏：保留有效前缀并报告损坏记录。
- 未知未来 schema：拒绝猜测恢复。

AgentLoop 在等待用户或进程退出时返回调用方；继续执行时从 SessionView 重新进入统一装配路径。

## 4. Context

Context 负责：

- System Prompt 与项目规则装配；
- Tool Schema 与 Provider 消息投影；
- Todo、Session 状态和 Memory 注入；
- 模型窗口、输出预留和 Token 预算；
- 长工具输出管理；
- 长会话压缩和 prompt-too-long 恢复；
- 向 CLI 说明预算、触发原因和压缩结果。

M6 开始前必须单独评审并冻结 Token 估算、预算水位、压缩层级、长结果管理、会话摘要和失败
回退协议。

Context 实现必须满足：

- Provider 消息不能包含孤立的 role=tool。
- Tool Call 与 ToolResult 保持完整配对。
- 尚未被模型成功消费的工具结果受到保护。
- 当前任务依赖的源码、Diff 和验证证据具有更高保留优先级。
- 压缩产物能够追溯到原始 Session Event。
- 压缩失败可以回退到上一个有效模型视图。

## 5. Memory

Memory 负责：

- 用户偏好、项目知识、工作流、决定和经验的长期保存；
- 用户显式保存与系统候选的控制流程；
- workspace、branch、path 和用户作用域；
- 来源 Session、Event、文件和验证证据；
- 来源变化后的重新验证、过期和遗忘；
- 检索、排序、Token 预算和注入格式。

M7 开始前必须单独评审并冻结 Memory 类型、状态机、存储、检索、用户控制和新鲜度协议。

Memory 实现必须满足：

- Memory 与 Session、Context 分离。
- 每条长期知识具有来源和作用域。
- 模型回答不能直接升级为已验证项目事实。
- 当前仓库证据优先于过期 Memory。
- 用户可以查看、接受、拒绝、刷新和删除 Memory。
- Memory 注入不能放宽 Workspace、权限或 Secret 边界。

## 6. 阶段验收

### M5：Session

- 重启后可以 list/resume/status。
- 权限等待能够恢复。
- started 工具恢复为 uncertain，副作用不会重复。
- SessionView 由唯一 Reducer 构造。

### M6：Context

- 长会话在目标模型预算内构造合法请求。
- 长结果压缩后原始事实仍可恢复或取回。
- prompt-too-long 使用有界恢复路径。
- CLI 可以说明本轮 Context 的预算和变化。

### M7：Memory

- 用户可以控制跨 Session 知识的保存和删除。
- 检索遵守作用域和 Token 预算。
- 来源变化后旧知识不再作为有效事实注入。
- Memory 存储损坏不能破坏 Session 恢复。
