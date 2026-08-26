# M5 设计

## 1. 数据流

```text
create turn
  -> AgentLoop
  -> JsonlSessionStore.append(fact)
  -> permission_pending
  -> process exits

resume session
  -> replay JSONL into SessionView
  -> claim permission request (fsync)
  -> ToolRegistry.prepare(original ToolCall)
  -> compare confirmation fingerprint
  -> execute once
  -> append ToolResult
  -> same AgentLoop continues
```

## 2. Durable facts

本里程碑使用 5 类 SessionEvent：

| kind | payload | reducer 结果 |
| --- | --- | --- |
| `turn_started` | turn id、prompt | 追加 user message |
| `message_appended` | ModelMessage | 追加 assistant/tool message |
| `usage_added` | TokenUsage | 累计 Session usage |
| `permission_pending` | PendingPermission | 注册未处理 request |
| `permission_claimed` | request id、choice | 移除未处理 request |

每行包含 `schema_version`、`kind`、`session_id`、`created_at` 和 `payload`。JSONL 文件是 Session 的唯一
持久化事实源；list/status 通过扫描与重放文件得到。

## 3. 恢复安全

`permission_claimed` 在副作用前 append、flush、fsync。claim 成功后，同一 request 不再可恢复。因此
进程中断后的结果是 at-most-once：恢复操作不会重放结果未知的副作用。

恢复时不反序列化工具私有对象。AgentLoop 使用原始 ToolCall 重新调用 `ToolRegistry.prepare`，并比较：

- Permission action、target、reason、metadata；
- preview 的 canonical JSON fingerprint。

匹配后使用本次 prepare 生成的可信 opaque plan 执行；不匹配时写入 `stale_snapshot` ToolResult，
再让模型继续解释结果。

## 4. Contracts

- `SessionStore`：消息与 Usage 的现有 contract。
- `PendingPermissionStore`：save、find-by-session、claim 三个方法。
- `SessionBackend`：组合以上两个 contract，供 AgentLoop 和 composition root 使用。
- `JsonlSessionStore`：Durable Session extension。

AgentLoop 不读取文件路径和 JSON；JSONL backend 不调用 Tool。

## 5. 文件布局

```text
<session-dir>/
  ses_<uuid>.jsonl
```

Session id 只接受本项目生成的固定格式。文件以 UTF-8 编码，每个事件占一行。当前运行模型是一个
Session 同时只有一个写入进程。

## 6. 失败语义

- Session 不存在：`unknown_session`。
- JSON/字段损坏：`corrupt_session`，包含文件和行号。
- request 已 claim 或不存在：`unknown_pending_permission`。
- 确认内容变化：ToolResult `stale_snapshot`，不执行副作用。
- append/fsync 失败：当前操作失败，副作用不会开始。
