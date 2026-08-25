# Coding Agent 项目总体方案草案

状态：`implemented-through-M4`

日期：2026-08-25

适用范围：v0.0.5 至 v0.1.0 的功能开发。M1 至 M4 已完成能力作为实现基线。

## 1. 项目定义

本项目是一套面向学习、讲解和作品展示的本地 CLI Coding Agent。它同时具备真实的代码读取、
修改、命令执行、权限确认、会话恢复、上下文管理和长期记忆能力，并将这些机制保留在可阅读、
可追踪的 Python 源码中。

用户可以从一次 CLI 任务出发，沿着源码和运行活动理解：

```text
用户输入
  -> 系统指令与项目规则装配
  -> Provider 请求与流式响应
  -> Agent Loop 判断文本或工具调用
  -> 工具参数校验与权限决策
  -> 文件或进程副作用
  -> Session 事实追加
  -> Context 投影与压缩
  -> Completion 判断
  -> 最终回答与可恢复状态
```

项目的交付单位不是一组彼此独立的 Demo，而是一套能够完成真实小型编码任务、并可按主路径
阅读的完整 Agent。

## 2. 产品目标

### 2.1 使用目标

- 用户可以在本地仓库启动交互式 CLI 或执行 one-shot 任务。
- Agent 可以搜索、读取、修改代码并运行项目命令。
- 工具调用、Diff、权限请求、压缩和记忆活动对用户可见。
- 进程退出后可以恢复 Session，不重复已经完成或结果不确定的副作用。
- 长会话在模型上下文限制内继续工作，原始 Session 事实仍可审计。
- 跨 Session 复用的项目知识具有来源、作用域和新鲜度状态。

### 2.2 学习目标

阅读者应能独立解释：

1. 一次模型请求如何构造，流式 Tool Call 如何累积。
2. Agent Loop 如何在模型、工具和用户输入之间切换。
3. 权限为什么是程序策略，而不是 System Prompt 承诺。
4. JSONL 如何重放为 SessionView，恢复为何不等于重新执行历史工具。
5. Context 如何从完整事实投影得到，并在预算压力下逐级压缩。
6. 长期 Memory 如何产生、确认、检索、过期和遗忘。
7. 模型输出、程序状态、工具证据和用户决定之间的信任边界。

### 2.3 工程目标

- 只有一个正式 Agent Loop。
- Provider SDK 对象不进入领域层。
- 文件和 Shell 副作用必须经过 Workspace、工具校验与权限管线。
- Session Event Log 是恢复所需的持久化事实源。
- Context 与 Memory 都是有来源的派生视图。
- CLI、Session、Provider、Tool、Permission、Context 和 Memory 可以分别测试。
- 核心 Python 源码保持在可通读规模，目标不超过约 25,000 行，不含测试和文档。

## 3. 开发基线与代码复用

### 3.1 当前基线

- M1 已完成 CLI、配置、Provider-neutral 类型与 OpenAI-compatible 流式请求。
- M2 已完成唯一 RuntimeRunner、Read/Glob/Grep、Workspace 与 Tool Registry。
- M3 已完成 AgentLoop、完整包边界、统一装配路径和交互式 CLI。
- M4 已完成 Edit/Shell/TodoWrite、权限暂停恢复、Diff 与安全写入。
- 现有 one-shot、交互式 CLI、JSON 输出、工具调用和测试作为后续开发的兼容基线。

### 3.2 复用原则

1. 成熟且符合当前边界的实现可以直接复用或修改复用。
2. 复用前读取它依赖的数据类型、调用方和对应测试，提取最小闭合依赖。
3. 进入本项目后统一包名、DTO、配置、错误语义和代码风格。
4. 每次迁移保持一个可运行纵向场景，不批量制造尚未接线的模块。
5. 公共 Agent 基础能力优先复用；Context 与 Memory 在对应里程碑单独完成设计评审。

## 4. 产品范围

### 4.1 v0.1.0 核心能力

- one-shot CLI：`agent -p "任务"`。
- 交互式 CLI：`agent`，支持连续输入和斜杠命令。
- OpenAI-compatible Provider；保留增加 Anthropic Provider 的接口。
- 流式文本、Usage、Tool Call 累积和 Provider 错误分类。
- `Read`、`Glob`、`Grep`、`Edit`、`Shell`、`TodoWrite`。
- Workspace 路径边界、文件快照、Diff 和原子写入。
- standard、plan、bypass 权限模式与 session-scoped grant。
- Append-only JSONL Session、list/resume/status 和协作式取消。
- 受预算约束的 Context 构造、渐进压缩和长会话恢复。
- 跨 Session Memory、用户控制、作用域检索和来源校验。
- 根目录 `AGENTS.md` 和分层 System Prompt 构造。
- CompletionGate 与验证证据。
- Rich/prompt-toolkit 终端展示；完整 TUI 作为后续产品层。

### 4.2 后续扩展

- Textual TUI。
- MCP stdio 客户端。
- 图片与附件。
- POSIX ShellAdapter。
- 只读工具并发和后台进程。
- 会话可视化重放器。
- 小型公开 Coding Task 评测。

## 5. 总体架构

```text
┌──────────────────────────────────────────────────────────────┐
│ CLI / Application                                           │
│ 参数、交互命令、依赖装配、活动展示                          │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ Agent                                                       │
│ 唯一 AgentLoop、工具流程、暂停/继续、停止与完成判断          │
└──────┬──────────────┬──────────────┬───────────────┬─────────┘
       ▼              ▼              ▼               ▼
  Context         Provider       Tool Host       Session Writer
       │                              │               │
       │                       Permission Policy      │
       │                              │               │
       │                          Workspace           │
       │                                              │
       └──────── SessionView / Memory Projection ─────┘
```

### 5.1 目录规划

```text
src/coding_agent/
  cli.py                  # 进程入口与参数
  app/                    # composition root、命令、交互式 CLI
  agent/                  # AgentLoop、tool flow、limits、completion
  runtime/                # cancellation、user input、运行活动事件
  protocol/               # Provider-neutral 跨边界 DTO
  providers/              # OpenAI-compatible 等 adapter
  tools/                  # Tool、Registry 与具体工具
  permissions/            # policy、manager、grants、request/decision
  workspace/              # path、snapshot、diff、atomic replace
  session/                # event、JSONL store、writer、reducer、resume
  context/                # prompt、projection、token budget、compaction
  memory/                 # store、retrieval、scope、freshness
  config/                 # TOML、环境变量、model/provider profile
tests/
  unit/
  contract/
  integration/
  e2e/
docs/
  architecture/
  guides/
  plans/
  proposals/
```

### 5.2 依赖方向

```text
cli -> app
app -> agent/session/context/providers/tools/permissions/memory/config
agent -> runtime/protocol + collaborator ports
context -> protocol/session view/memory projection
providers -> protocol
tools -> protocol/workspace
permissions -> protocol + permission types
session -> protocol + session domain types
memory -> session references + memory domain types
```

硬约束：

- Provider、Tool、Permission 和 Workspace 不导入 AgentLoop。
- CLI 通过 Application service 使用运行时，不读取 AgentLoop 私有状态。
- Session 创建、恢复和继续经过同一个 bootstrap/composition path。
- Context 不修改 Session 原始事件；Memory 不承担 Session 恢复。
- 权限决定不能由模型文本、项目规则文件或 Memory 放宽。

## 6. 一次任务的完整运行链路

```text
1. CLI 解析参数、配置和 Workspace
2. App 创建或恢复 Session
3. AgentLoop 写入 user_message 事实
4. ContextBuilder 装配 System Prompt、项目规则、Memory 和 Session 投影
5. Provider 流式返回文本、reasoning、Tool Call 和 Usage
6. 完整 assistant 消息写入 Session
7. Tool Host 验证工具名称与参数
8. PermissionManager 计算 allow / ask / deny
9. ASK 时写入 pending request，AgentLoop 返回调用方
10. ALLOW 时执行 Tool，并写入 requested/started/final 生命周期
11. ToolResult 配对写入后回到 ContextBuilder
12. 模型不再调用工具时执行 CompletionGate
13. 写入 terminal event，并向 CLI 返回 TurnResult
```

### 6.1 关键不变量

- 流式 Tool Call 参数完成前不能执行。
- assistant Tool Call 必须先于同 ID 的 ToolResult。
- 一个 Tool Call 最多有一个最终 ToolResult。
- 每个 started 副作用必须结算为 completed、failed、cancelled 或 uncertain。
- 权限恢复只能使用 Session 保存的原始 Tool Call。
- 已完成和 uncertain 的副作用都不能自动重放。
- 模型声称成功不能替代文件状态、命令退出码和验证记录。

## 7. CLI 与运行活动

### 7.1 命令入口

```text
agent                         # 交互式 CLI
agent -p "task"              # 单次任务
agent --cwd <path>            # 指定 Workspace
agent --resume <session-id>   # 恢复 Session
agent sessions               # 列出 Session
agent status <session-id>     # 查看终态、pending 和 usage
agent config show             # 脱敏配置
agent -p "task" --json       # 机器可读结果
```

### 7.2 交互活动

普通 CLI 按时间顺序展示：

- 模型文本流；
- 工具名称、参数摘要和执行结果；
- 文件 Diff 与快照状态；
- 权限问题和可选决定；
- Session 保存、恢复和压缩活动；
- Token 预算与压缩级别；
- Memory 候选、采用和失效；
- 最终验证状态和停止原因。

展示层消费结构化 RuntimeEvent，不负责推导领域事实。

## 8. System Prompt 与项目指导

Model Request 由 ContextBuilder 每轮装配。System Prompt 按以下层级组织：

1. 核心 Agent 身份与行为规则；
2. Runtime 能力、权限边界和完成要求；
3. 根目录 `AGENTS.md` 项目指导；
4. 当前 Todo、Session 摘要状态和检索到的 Memory。

当前用户任务和真实消息 tail 进入 messages；工具 Schema 通过 Provider 原生 tools 字段传递，
不复制进 System Prompt。

项目规则和 Memory 都不能：

- 修改权限模式；
- 扩大 Workspace；
- 读取 Secret；
- 绕过 Tool Schema；
- 覆盖更高层运行时指令。

CLI 显示已加载项目规则的相对路径、内容哈希和优先级。

## 9. Provider 设计

内部协议至少包含：

- `ModelMessage`、`ModelRequest`；
- `TextDelta`、`ReasoningDelta`、`ResponseCompleted`；
- `ToolDefinition`、`ToolCall`、`ToolResult`；
- `TokenUsage`、`ProviderCapabilities`、`ProviderErrorKind`。

Provider Adapter 负责：

- 厂商消息与工具格式转换；
- 流式文本和 Tool Call 分片累积；
- reasoning 字段回放；
- Usage 解析；
- 认证、限流、网络、超时和 prompt-too-long 分类。

Provider Adapter 不负责 Session、权限、工具执行、Context 压缩和重试副作用。

## 10. 工具系统

### 10.1 Tool 合同

每个 Tool 声明：

- 名称与描述；
- 参数 Schema；
- 副作用类别；
- Permission spec；
- 输出预算；
- 是否支持取消；
- 是否允许并发。

错误通过结构化 ToolResult 返回模型；编程错误保留为运行时失败，不能伪装成工具业务错误。

### 10.2 核心工具

| Tool | 能力 | 主要约束 |
| --- | --- | --- |
| Read | 按行读取文本 | UTF-8、行数与字节预算 |
| Glob | 文件发现 | Workspace 内、稳定排序 |
| Grep | 内容搜索 | 结果数量与字符预算 |
| Edit | 创建、替换、Patch、删除 | snapshot、Diff、权限、原子替换 |
| Shell | PowerShell 命令 | cwd、timeout、输出预算、逐次确认 |
| TodoWrite | 任务状态 | revision 与状态转换校验 |

## 11. 权限与副作用安全

### 11.1 权限模式

- `standard`：读取默认允许；文件变更按作用域确认；Shell 每次确认。
- `plan`：只允许读取、搜索、计划和说明，不执行副作用。
- `bypass`：用于明确受控环境；继续记录 Tool、Diff 和 Session 事实。

### 11.2 权限决定

- `ALLOW_ONCE`
- `ALLOW_SESSION`
- `DENY`
- `ASK`

文件授权可以限定到 Workspace 相对路径或目录；Shell 不保存 session-wide 自动授权。

### 11.3 Edit 链路

```text
Schema 校验
  -> Workspace.resolve
  -> 读取当前内容与哈希
  -> 构造候选内容
  -> 生成可信 unified diff
  -> 权限或 review
  -> 再次比较快照
  -> 同目录临时文件
  -> flush/fsync
  -> atomic replace
  -> 返回新哈希与变更统计
```

### 11.4 Shell 链路

- P0 使用 Windows PowerShellExecutor。
- 每次执行记录原始命令、cwd、timeout、退出码和截断信息。
- standard 模式下每次 Shell 都进入 ASK。
- CommandInspection 可以展示管道、重定向、变量和子表达式等结构特征。
- 超时触发进程树终止，并把真实终止结果写入 ToolResult。

权限系统降低意外副作用风险，不提供 OS 级安全隔离。

## 12. Session 与恢复

### 12.1 持久化模型

```text
<workspace>/.coding-agent/
  sessions/<session-id>.jsonl
  artifacts/<session-id>/...
  permissions.json
  memory/...
```

Session JSONL 是 append-only 事实日志。每个事件至少包含：

- schema version；
- event/session/turn ID；
- 单调 sequence；
- timestamp；
- event type；
- versioned payload。

### 12.2 最小事件注册表

| Event | 事实 |
| --- | --- |
| `session_created` | Session、Workspace 和配置身份 |
| `user_message` | 用户提交及附件元数据 |
| `assistant_message` | 完整文本、reasoning 与 Tool Call |
| `tool_lifecycle` | requested/started/completed/failed/denied/cancelled/uncertain |
| `permission_requested` | 等待用户决定的原始请求引用 |
| `permission_decided` | 用户决定和授权作用域 |
| `user_input` | ask_user 等非权限输入的 requested/answered 状态 |
| `todo_updated` | 带 revision 的完整 Todo 快照 |
| `context_changed` | 外置结果、压缩替换和会话摘要 |
| `turn_terminal` | status、stop reason、Usage 和验证信息 |

流式 delta、spinner、工具开始提示等展示活动属于 RuntimeEvent，不进入 Session 重放。

### 12.3 SessionView

Reducer 从完整事件重放得到：

- 有效消息；
- 工具调用及结算状态；
- pending permission/user input；
- Todo；
- Context checkpoint；
- Usage；
- terminal state。

CLI、resume、ContextBuilder 和 Session export 使用同一 SessionView，不分别解释 JSONL。

### 12.4 恢复规则

- requested 但未 started：恢复为待处理，不自动执行。
- started 但无终态：追加 uncertain，不自动重放。
- completed/failed/denied：只恢复结果。
- 权限等待：重建请求并等待用户决定。
- JSONL 最后一行损坏：保留有效前缀，报告并隔离损坏尾部。
- 未知未来 schema：拒绝猜测恢复。

AgentLoop 不跨用户等待或进程退出保存可变调用栈；暂停产生终态并 return，继续从 SessionView
重新进入统一装配路径。

## 13. Context 职责边界

Context 负责从 SessionView 构造单次 Provider 请求。它管理 System Prompt、项目规则、工具
Schema、当前任务状态、Memory 投影、消息历史和输出预留，但不修改 Session 原始事件。

Context 阶段必须解决：

- 不同模型的上下文窗口与 Token 估算；
- Tool Call 与 ToolResult 的消息合法性；
- 长工具输出的有界展示与原文取回；
- 长会话的渐进压缩和 prompt-too-long 恢复；
- 压缩前后事实来源、当前任务证据和恢复能力；
- 用户可观察的预算、触发原因和压缩结果。

在 M6 开始前单独评审 Context 设计文档，届时冻结 Token 估算、预算水位、压缩层级、
大型结果管理、会话摘要和失败回退的具体协议。M6 实现必须继续满足以下边界：

- 压缩只改变 Provider 视图，不删除 Session 事实；
- Provider 消息不能包含孤立的 role=tool；
- Tool Call 与 ToolResult 必须保持配对；
- 尚未被模型成功消费的工具结果受到保护；
- 当前任务依赖的源码、Diff 和验证证据具有更高保留优先级；
- 压缩产物能够追溯到原始 Session Event。

## 14. Memory 职责边界

Memory 负责跨 Session 保存值得复用的用户偏好、项目知识、工作流、决定和经验。它不保存完整
聊天记录，也不参与 Session 恢复。

Memory 阶段必须解决：

- 什么内容具备长期复用价值；
- 用户显式记忆、系统候选和审核流程；
- Workspace、branch、path 和用户级作用域；
- 来源 Session、Event、文件和验证证据；
- 来源变化后的重新验证、过期和遗忘；
- 检索排序、Token 预算和注入格式；
- 持久化事实与可重建检索索引的分工。

在 M7 开始前单独评审 Memory 设计文档，届时冻结类型、状态机、存储格式、检索算法、审核
入口和新鲜度策略。M7 实现必须继续满足以下边界：

- Memory 与 Session、Context 分离；
- 每条长期知识具有来源和作用域；
- 模型回答不能直接升级为已验证项目事实；
- 当前仓库证据优先于陈旧 Memory；
- 用户能够查看、接受、拒绝、刷新和删除 Memory；
- Memory 不能提高指令权限或放宽工具安全策略。

## 15. Todo 与 CompletionGate

Todo 使用 revision 和四状态：`pending`、`in_progress`、`completed`、`blocked`。

CompletionGate 检查：

- 是否存在未结算 Tool Call；
- 是否仍在等待权限或用户输入；
- 是否存在未处理的 pending/in_progress Todo；
- 最近一次修改之后是否存在验证证据；
- 是否达到有界补救次数或运行限制。

验证状态来自 Shell/Test ToolResult 的命令、退出码和时间关系，不根据模型文本推断。

## 16. 测试与验证方案

### 16.1 测试分层

| 层级 | 目标 | 代表范围 |
| --- | --- | --- |
| Unit | 单个纯模块和状态转换 | reducer、budget、policy、memory freshness |
| Contract | 跨边界 DTO 和 adapter | Provider 流事件、Tool Schema、Session schema |
| Integration | 多模块协作 | AgentLoop + temp workspace + permissions/session |
| E2E | 用户入口 | CLI 读取、修改、确认、恢复和 JSON 输出 |
| Regression | 已发现缺陷和不变量 | stale write、orphan tool、uncertain recovery |
| Real-provider smoke | 实际服务兼容性 | 发布前人工运行固定任务 |

测试替身包括脚本化 Provider、临时 Workspace、内存 Permission UI 和故障可控的 ToolExecutor；
它们服务于模块和端到端测试，不改变产品架构。

### 16.2 核心测试集

- Agent Loop 文本、单工具、多工具、拒绝、取消和限制。
- Provider request/stream/tool-call/usage/error contract。
- Read/Glob/Grep/Edit/Shell/Todo 的正常与错误行为。
- Workspace 越界、symlink、stale snapshot 和原子替换。
- Permission allow/ask/deny、grant scope 和 resume。
- JSONL append、尾部损坏、reducer、pending/uncertain 恢复。
- Context 预算、消息合法性、长结果管理、压缩和恢复。
- Memory scope、用户控制、来源变化和过期过滤。
- CLI stdout/stderr、退出码、交互命令和 clean install。

### 16.3 CI 门禁

```text
uv sync --locked
ruff check
basedpyright
pytest tests/unit
pytest tests/contract
pytest tests/integration
pytest tests/e2e
uv build
isolated wheel install
agent --help
docs link and import-boundary checks
```

## 17. 开发流程

### 17.1 每个模块的进入流程

```text
用户可观察行为
  -> 现有实现与接口审阅
  -> 本项目接口和状态归属
  -> 正常、失败、暂停和恢复语义
  -> 最小纵向实现
  -> Unit/Contract
  -> Integration/E2E
  -> CLI 演示
  -> 阅读指南与 Closeout
```

### 17.2 代码复用与迁入流程

1. 读取待复用源码、相邻类型、调用方和对应测试。
2. 提取当前功能所需的最小闭合依赖集合。
3. 复制后立即适配本项目包名、DTO、错误和配置。
4. 迁入或重写对应测试，确认行为一致。
5. 通过当前纵向 CLI 场景后才进入主分支。

### 17.3 提交单位

一个提交应完成一个可解释的纵向或模块边界，例如：

- runtime cancellation + AgentLoop 使用；
- PermissionRequest + policy + 一个 Edit preflight；
- Session event + writer + replay test；
- Context budget + projection + CLI 活动；
- Memory create + user control + retrieval。

## 18. 路线图

### 已完成：M1，v0.0.1

- CLI、配置和 Provider-neutral 基础类型。
- OpenAI-compatible 与文本流式输出。
- JSON 结果契约。

### 已完成：M2，v0.0.2

- 唯一 RuntimeRunner。
- Read、Glob、Grep、Workspace 和 Tool Registry。
- 流式 Tool Call 与运行限制。

### 已完成：M3，架构骨架与交互式 CLI，v0.0.3

- 建立 app/agent/runtime/session/context/memory/permissions 包边界。
- 将当前 Runner 收敛到 `agent/AgentLoop`，runtime 只保留中立原语。
- 建立 composition root 和 SessionBootstrap 接口。
- 使用 InMemorySessionStore、基础 ContextBuilder、ReadOnlyPermissionPolicy 和
  EmptyMemoryRetriever 跑通现有纵向场景，使所有核心包进入真实调用链。
- 增加 prompt-toolkit + Rich 交互式 CLI 与结构化活动流。
- 保持 M2 读取仓库的完整纵向场景继续运行。

退出标准：目录与依赖边界稳定；交互式和 one-shot 共用同一 AgentLoop；没有空转的第二实现。

### M4：写工具与权限，v0.0.4

- Edit、Shell、TodoWrite。
- Permission policy/manager/grants。
- Diff、snapshot recheck 和 atomic replace。
- plan/standard/bypass。

退出标准：CLI 可以修改一个文件、确认 Diff、运行测试并阻止 stale write。

### M5：Session 与恢复，v0.0.5

- JSONL event、writer、reducer 和 SessionView。
- list/resume/status。
- 权限等待恢复、Ctrl-C 和 uncertain tool settlement。

退出标准：在权限等待和工具 started 两处中断后，重启进程得到正确且不重复副作用的状态。

### M6：Context 工程，v0.0.6

- 完成 Context 详细设计评审并冻结预算、压缩和恢复协议。
- 实现模型上下文预算、消息合法投影和压缩触发。
- 实现大型工具结果管理、长会话压缩和 prompt-too-long 恢复。
- 在 CLI 展示预算、触发原因、压缩结果和来源关系。

退出标准：长会话压缩后 Provider 消息合法、原始事实可取回、Token 预算低于目标水位。

### M7：Memory 与完成判断，v0.0.7

- Todo 状态机与 CompletionGate。
- 完成 Memory 详细设计评审并冻结类型、状态、存储、检索与失效协议。
- 实现 Memory 的创建、用户控制、作用域检索、来源校验和过期处理。
- 提供 Memory 查看、保存、刷新和删除命令。
- AGENTS.md 和 Skills 渐进加载。

退出标准：跨 Session 取回已接受 Memory；来源变化后旧事实不再作为有效项目知识注入。

### M8：可阅读版本发布，v0.1.0

- CLI 体验、配置、错误信息与安装流程收口。
- OpenAI-compatible 真实 Provider 场景验收。
- 完整架构文档、代码阅读路线和一轮 Turn Trace。
- 三个固定演示：理解仓库、修改并验证、恢复长会话并使用 Memory。
- 源码规模、依赖边界、测试和文档发布报告。

## 19. M3 实施记录

1. 冻结核心包职责、公共类型和迁移顺序。
2. 建立 `app/`、`agent/`、`runtime/`、`session/`、`context/`、`memory/`、
   `permissions/` 包目录及最小可执行实现。
3. 将 RuntimeRunner 迁移为 AgentLoop，保留兼容导出并删除重复循环入口。
4. 引入 cancellation、user input 和 RuntimeEvent。
5. 建立 composition root、SessionBootstrap、InMemorySessionStore、基础 ContextBuilder、
   ReadOnlyPermissionPolicy 和 EmptyMemoryRetriever。
6. 把现有 Provider、Workspace 和只读工具接入新装配路径。
7. 增加交互式 CLI、活动渲染和 `/help`、`/exit`。
8. 建立新的 tests/unit、contract、integration、e2e 分层入口。
9. 补充架构阅读指南和 M3 Closeout。

M3 的所有新包必须由当前“读取仓库并回答”纵向场景实际经过；只有未来接口而没有调用路径的
模块不计为已完成。

## 20. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 复用代码后依赖面迅速扩大 | 最小闭合依赖、聚焦测试和纵向场景验收 |
| 复用类型与当前协议形成两套模型 | 迁入时统一 DTO，并用 contract test 锁定 |
| 架构整理破坏 M1/M2 行为 | 保留 CLI E2E 和兼容导出，按纵向切片迁移 |
| Session/Context/Memory 状态重叠 | Session 事实、Context 投影、Memory 派生三层归属表 |
| Context 压缩造成信息丢失 | 消费状态、来源关系、压缩边界和失败回退 |
| Memory 污染后长期误导模型 | 用户控制、来源校验、作用域和过期状态 |
| 权限 UI 与执行 payload 不一致 | 本地保存原始 Tool Call，UI 只返回 request ID 与决定 |
| CLI 展示逻辑渗入 Runtime | 结构化 RuntimeEvent + renderer 端口 |

## 21. 方案状态

已经确认：

- 产品定位为真实可运行、可阅读的 CLI Coding Agent。
- 成熟实现可以直接复用或修改复用，并统一到本项目架构。
- v0.1.0 以 Rich/prompt-toolkit CLI 为正式界面。
- Textual TUI 进入后续产品阶段。
- M3–M8 路线图作为后续开发主线。

阶段性设计：

- Context 的模块职责、信任边界和成功标准已经确定；具体预算与压缩协议在 M6 评审。
- Memory 的模块职责、用户控制和来源原则已经确定；具体数据与检索协议在 M7 评审。

开放决定：

- 项目名称；
- Python 包名；
- CLI 命令；
- 最终许可证。

下一步建立 M4 文档包，先冻结 Edit preview/snapshot/stale-write 与权限暂停协议，再实现写工具
和权限纵向场景。
