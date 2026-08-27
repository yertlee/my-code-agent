# Session、Context 与 Memory 扩展边界

## 1. 三类能力

| 能力 | 回答的问题 | 当前状态 | Kernel seam |
| --- | --- | --- | --- |
| Session | 当前对话发生了什么？ | 内存或 JSONL 事实重放 | `SessionBackend` |
| Context | 下一次模型看到什么？ | deterministic 预算压缩投影 | `ContextBuilder` + `ContextStrategy` |
| Memory | 新会话复用什么知识？ | JSONL 项目事实主线 | `MemoryService` |

三者具有独立生命周期：Session 保存事实，Context 生成本次模型视图，Memory 保存带来源的跨会话知识。

## 2. 当前 v0.0.7

`InMemorySessionStore` 用于默认轻量运行；`JsonlSessionStore` 在指定 `--session-dir` 时保存 durable
Session。两者都实现 `SessionBackend`，AgentLoop 不感知存储介质。

JSONL 使用 5 类事实：

- `turn_started`；
- `message_appended`；
- `usage_added`；
- `permission_pending`；
- `permission_claimed`。

唯一 reducer 从事实重建 messages、累计 Usage 和未处理 Permission。Session list/status 通过目录扫描
和同一个 reducer 得到。

## 3. 权限恢复

等待权限时，Session 保存原始 ToolCall、remaining calls、PermissionRequest、preview fingerprint 和
Turn 计数。恢复流程为：

```text
find pending
  -> append + fsync permission_claimed
  -> re-prepare original ToolCall
  -> verify confirmation fingerprint
  -> execute prepared Tool once
  -> append ToolResult
  -> continue AgentLoop
```

claim 位于副作用之前，使跨进程恢复保持 at-most-once。文件或确认预览发生变化时返回
`stale_snapshot` ToolResult，AgentLoop 继续让模型解释结果。

## 4. Context strategy

ContextBuilder 负责组装 ModelRequest，ContextStrategy 负责在预算内选择事实投影。默认 deterministic
策略执行 ToolResult 头尾压缩、完整回合淘汰和明确超限停止；它只改变下一次 ModelRequest，不修改
Session JSONL 事实。

替代压缩方式通过 ContextStrategy 接入，不改变 AgentLoop 或 Session。

## 5. Memory extension

MemoryService 顶层 contract 提供保存、检索、查看、失效和删除带来源项目知识的主线。
MemoryService 内部组合 MemoryLedger、MemoryWriter 和 MemoryRetriever；默认实现使用 JSONL 账本、
显式写入、确定性证据候选和关键词/新鲜度检索。

Memory 作为 Context 输入，不参与 Tool 恢复，也不改变 Workspace 与 Permission 判断。

## 6. 依赖关系

```text
SessionBackend -> SessionSnapshot + PendingPermission
MemoryService -> MemoryRecall + MemoryWriteResult
ContextBuilder -> SessionSnapshot + MemoryRecall -> ModelRequest
MemoryLedger/Writer/Retriever -> MemoryService internal composition
```

Context 和 Memory 扩展依赖公开 DTO，不访问 AgentLoop 私有字段。
