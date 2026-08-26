# Session、Context 与 Memory 扩展边界

## 1. 三类能力

| 能力 | 回答的问题 | 当前状态 | Kernel seam |
| --- | --- | --- | --- |
| Session | 当前对话发生了什么？ | 内存消息与 Usage | `SessionStore` |
| Context | 下一次模型看到什么？ | System Prompt + Session messages | `ContextBuilder` |
| Memory | 新会话复用什么知识？ | 尚未进入产品源码 | M7 创建 |

三者按独立里程碑实现，避免一个“状态系统”同时承担历史、模型预算和长期知识。

## 2. 当前 v0.0.4

`InMemorySessionStore` 保存同一 Application 进程内的 messages 和累计 Usage。`BasicContextBuilder`
把 System Prompt、Session messages 和 Tool definitions 构造成 ModelRequest。

当前没有 durable Session、Context 压缩或 Memory contract。CLI 退出后不会恢复内存状态。

## 3. Durable Session extension

M5 只需要证明一件事：JSONL 事实能够重放为 SessionView，并让同一 AgentLoop 继续权限等待。

必须保持：

- JSONL 是唯一持久化事实；
- SessionView 只有一个 reducer；
- 已结算 ToolResult 不重复执行；
- started 且无结果的副作用不会自动重放；
- list/status 直接扫描 Session 事实。

事件 schema、CLI 命令和恢复失败在 M5 scope 中冻结，不在当前 Kernel 预留类型。

## 4. Context strategy extension

M6 通过替换 ContextBuilder 增加 Token 估算、长结果处理和一种渐进压缩策略。它只能改变下一次
ModelRequest，不修改 Session 原始事实。

TokenEstimator、预算阈值和压缩输出在 M6 用真实模型实验确定。

## 5. Memory extension

M7 创建 Memory contract，完成一个显式用户故事：保存、检索、查看和删除一条带来源的项目知识。

Memory 具备独立生命周期和作用域；它作为 Context 输入，不参与未完成 Tool 的恢复，也不能放宽
Workspace 或 Permission。

## 6. 依赖关系

```text
SessionStore -> SessionSnapshot / SessionView
ContextBuilder -> Session view + optional extension inputs -> ModelRequest
MemoryStore -> validated memory items -> ContextBuilder
```

Context 和 Memory 扩展依赖公开状态 DTO，不访问 AgentLoop 私有字段。
