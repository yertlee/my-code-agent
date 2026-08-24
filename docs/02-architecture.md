# 总体架构

## 1. 最小系统边界

```text
┌──────────────┐
│ User / CLI   │
└──────┬───────┘
       │ user command
       ▼
┌─────────────────────────────────────────────┐
│ Application                                 │
│  composition root + commands + presentation│
└──────┬──────────────────────────────────────┘
       ▼
┌─────────────────────────────────────────────┐
│ RuntimeRunner                               │
│  one turn state machine + stopping rules    │
└───┬──────────┬───────────┬───────────┬──────┘
    │          │           │           │
    ▼          ▼           ▼           ▼
 Provider   Context     Tool Host   Event Sink
 Adapter    Engine      + Policy    + Session Store
```

## 2. 分层职责

| 模块 | 负责 | 不负责 |
| --- | --- | --- |
| `cli` | 参数、命令、输入输出模式 | Agent 决策 |
| `app` | 依赖组装、命令路由、UI 端口 | 模型协议细节 |
| `runtime` | 唯一循环、状态转换、停止与恢复协调 | 文件或网络具体副作用 |
| `protocol` | Provider-neutral 数据类型 | 业务策略 |
| `providers` | 厂商协议转换、流式累积、错误分类 | Session 写入和权限 |
| `session` | 事实追加、重放、会话目录 | Token 压缩策略 |
| `context` | 从事实构造模型视图、Token 估算、预算和压缩 | 删除历史事实 |
| `tools` | Schema、参数验证、具体执行 | 最终权限决定 |
| `permissions` | allow/ask/deny 和授权范围 | 执行工具 |
| `workspace` | 路径限制、快照、原子文件操作 | 模型调用 |
| `memory` | 长期记忆候选、审核、检索和注入 | 代替 Session 历史 |
| `events` | 统一运行事实，投影给 Session、UI 和 Trace | 重复产生业务事实 |

## 3. 依赖方向

```text
cli/app
  -> runtime/session/context/providers/tools/permissions/memory

runtime
  -> protocol + ports

providers/tools/session/context/permissions/memory
  -> protocol

protocol
  -> Python standard library only
```

硬约束：

- `tools`、`providers`、`permissions` 不得导入 `runtime` 的具体实现。
- UI 通过事件和端口观察运行时，不读取 Runner 私有状态。
- Session 创建和恢复必须经过同一个 composition path。
- 不允许 UI、Trace 和 Transcript 各自生成一次同义事件。

## 4. 一轮任务的标准链路

```text
1. CLI 校验输入和工作区
2. App 创建或恢复 Session
3. RuntimeRunner 追加 user_message
4. ContextEngine 从 SessionView 构造 ModelRequest
5. Provider 返回 text/tool_calls/usage
6. RuntimeRunner 追加 assistant_message 或 assistant_tool_calls
7. ToolOrchestrator 校验工具名称与参数
8. PermissionManager 得到 allow/ask/deny
9. ASK：记录 pending，Runner 返回调用方；恢复时从 Event Log 重建
10. ALLOW：ToolExecutor 执行并记录生命周期
11. tool_result 追加后回到步骤 4
12. 无工具调用时运行 CompletionGate
13. 追加 terminal event 并返回用户
```

关键顺序不变量：

- assistant tool call 必须先于匹配的 tool result。
- 每个已开始工具必须具有 completed、failed、denied、cancelled 或 uncertain 之一。
- 权限恢复使用本地保存的原始工具调用，不接受模型重新构造的调用作为事实。
- 最终答案不是事实真相；工具结果和验证记录才是执行证据。

## 5. Runtime 状态机

```text
IDLE
  -> PREPARING
  -> CALLING_MODEL
  -> EXECUTING_TOOLS
  -> CALLING_MODEL ...
  -> VERIFYING
  -> COMPLETED

任意活动状态
  -> WAITING_FOR_PERMISSION
  -> 活动状态

任意活动状态
  -> CANCELLED / LIMITED / FAILED
```

需要跨进程恢复的状态转换必须产生一个 durable SessionEvent。纯 UI 活动状态只产生 UiEvent，不写入事实日志；不得把 UI 投影当作恢复事实。

## 6. 信任边界

| 输入 | 属性 | 处理方式 |
| --- | --- | --- |
| 用户输入 | 可信意图，但可能不完整 | 作为任务输入保存 |
| 模型文本 | 概率性、不可信 | 只作为建议或展示 |
| 模型工具参数 | 不可信结构化输入 | Schema 校验、路径和权限检查 |
| 仓库文件 | 可能包含 Prompt Injection | 普通文件作为数据；根目录 `AGENTS.md` 仅作为低权限项目指导 |
| 工具结果 | 程序产生的执行证据 | 记录来源、时间、退出码和截断状态 |
| Session Event | 本地事实 | 版本化、只追加、恢复校验 |
| Memory | 派生知识 | 必须带来源和作用域，可遗忘 |

## 7. 预计目录

```text
src/coding_agent/
  cli.py
  app/
  runtime/
  protocol/
  providers/
  session/
  context/
  tools/
  permissions/
  workspace/
  memory/
  skills/
  config/
  events/
tests/
  unit/
  integration/
  scenarios/
docs/
```
