# 参照 FirstCoder 骨架的翻译式重写计划

> 决策记录：以当前仓库 `coding-agent` 为底，按 FirstCoder 架构骨架重搭，核心模块翻译式重写。
> FirstCoder 参考实现：`docs/reference/firstcoder-architecture.md`（2,534 行拆解，章节号「FC:x」即引用该文档）。

## 0. 目标与边界

- **不做**：推翻重来。保留已达标层，只重写事实层与 context 层，并对齐 provider seam。
- **做**：一次性把 Session 事实层升级到 FirstCoder 的 `AgentMessage/MessagePart` 事实账本，
  把 ContextBuilder 扩展成 budgeted 投影，再把压缩系统建在新事实模型上。
- **不留技术债**：不再"先用 flat 模型 + 流式 provider，之后再加"。

## 1. 三层判断（对齐结果）

### 第一层 · 已达标、基本留用（~70%）

| 模块 | 现状 | 结论 | 依据 |
|---|---|---|---|
| `providers/` 抽象 | `ChatProvider.stream` + `ModelStreamEvent`（流式） | **接口对齐 FC**，改为 complete + stream 双形态 | FC:6、FC:17.1 |
| `permissions/` | Manager/Policy/Mode，与 FC 同构 | 留用 | FC:7、FC:16.6 |
| `runtime/` | cancellation + events | 留用（补齐 UserInputRequest 可选） | FC:13、FC:16 |
| `workspace/` | 路径边界 | 留用 | FC:15 |
| `tools/` contract + registry | prepare/execute + preflight | 留用 | FC:11.1 |
| 测试纪律 / guardrails | 49 项测试 | 留用 | FC:8 |

### 第二层 · 必须重写 / 引入新结构

| 模块 | 现状 | 目标 | 依据 |
|---|---|---|---|
| session 事实层 | flat `ModelMessage` | **`AgentMessage/MessagePart`（带 id/metadata）+ JSONL codec** | FC:4、FC:16.1 |
| context 层 | `BasicContextBuilder` 直接投影全部消息 | **budget + lifecycle + compaction 的预算化投影** | FC:9、FC:16.3 |
| loop 消息处理 | flat `ModelMessage` 直发 | **读事实 → 投影 → 发请求** | FC:5、FC:16.2 |
| provider seam | 纯流式 `stream()` | **`complete()` + `stream()` 双形态** | FC:6 |

### 第三层 · 不搬（FirstCoder 特有）

benchmark 门禁（`execution_evidence` / `stagnation`）、Terminal-Bench、yuren 彩蛋、
TUI 动画细节、MCP 搜索激活。

## 2. 目标骨架

```
cli.py / app/ (interactive + one-shot)
   -> AgentApplication
   -> AgentLoop
        -> ContextBuilder (budgeted projection)
             -> Session facts (AgentMessage/MessagePart, JSONL)
        -> ChatProvider (complete + stream)
        -> ToolRegistry -> Tool plugins (prepare/execute + preflight)
        -> PermissionManager -> PermissionPolicy
        -> RuntimeEvent / EventSink
   -> TurnResult
```

核心不变式（对齐 FC：16.1）：
- **Session facts = 真实发生过的消息、工具调用、工具结果、权限状态**（只追加，不篡改）
- **Context projection = 每次请求真正发给模型的、预算内的消息视图**（压缩只影响视图）
- **二者分离**：压缩永不修改 JSONL 事实；从同一份事实可重建不同上下文

## 3. 分阶段迁移（每阶段测试绿）

### Stage 0 · 冻结目标骨架（本文档）

### Stage 1 · Session 事实层升级

- 引入 `AgentMessage/MessagePart`（带 `id`、`metadata`，`PartKind` 含
  `text/tool_call/tool_result`）
- 更新 `SessionEventKind` / JSONL codec / `JsonlSessionStore` reducer
- 更新 `SessionSnapshot`、`SessionBackend`、`InMemorySessionStore`
- **事实消息写入 `turn_id`，工具结果写入 metadata**（`ok`、`tool_name` 等）—— 这是
  lifecycle 与完整工作轮次的原料
- 迁移 loop 的 append 路径（写事实而非 flat message）
- 测试：durable session、JSONL codec、reducer 全绿

### Stage 2 · Provider seam 对齐

- `ChatProvider` 改为 `complete()` + `stream()` 双形态（对齐 FC:6）
- `providers/base.py`、`providers/streaming.py`、openai_compatible、fake 适配
- 测试：provider 双形态、流式事件、错误分类全绿

### Stage 3 · Context 投影管线

- `TokenEstimator`（复刻 FC `estimate_text_tokens`，字符数÷4，不绑 tokenizer）
- `ContextBudget`（窗口 / 输出预留 / 水位 L1=70% L2=85% L3=95%）
- `BudgetedContextBuilder`：system + 当前任务 + 未完成状态 + 最近轮次 + 压缩后的旧结果
- 测试：`test_context_budget.py`、`test_context_projection.py`

### Stage 4 · 压缩语义（lifecycle + L1-L3）✅

- `ToolResultLifecycle`（对齐 FC:9.4）：FRESH/STALE/SUPERSEDED/DERIVED/DUPLICATE，
  用事实顺序与工具 metadata 推导（read 覆盖 / mutation 失效）
- L1 将单条超长 ToolResult 压至输入预算的 20%（头尾保留 + 省略标记）；L2 淘汰
  最旧完整轮次；L3 明确停止（`context_budget_exceeded`）
- 核心保护区：当前任务 / pending / 最近修改验证 / 工具配对
- 测试：`test_context_compaction.py` 与 `test_context_projection.py`

### Stage 5 · CLI / 渲染 / 可观测性 ✅

- `CONTEXT_PROJECTED` 事件的压缩摘要进入 `TurnResult` / JSON / stderr 提示
- `--context-window` 覆盖 `CODING_AGENT_CONTEXT_WINDOW`
- 测试：CLI JSON、配置优先级与终端超限提示

## 4. M6 十项产品决策（本计划必须遵守）

| # | 决策 | 结论 |
|---|---|---|
| 1 | 默认窗口 | 32k（`CODING_AGENT_CONTEXT_WINDOW` 可覆盖） |
| 2 | 输出预留 | 4k 常量，溢出边际给输入 |
| 3 | 压缩目标 | 当前任务 > 工具证据链 > 可重建历史 |
| 4 | L1 规则 | 单条 ToolResult 为单位；超长判定用估算器；头尾保留 + 显式省略 |
| 5 | L2 单位 | 完整工作轮次，跨 tool_calls 成批保留；用户消息为边界 |
| 6 | 核心保护区 | 当前任务 / pending / 最近修改验证 / 工具配对，永不拆散 |
| 7 | L3 行为 | 明确停止 `context_budget_exceeded`，不做自动模型摘要 |
| 8 | 可观察性 | CLI 提示 + JSON 摘要 + `CONTEXT_PROJECTED` 事件 |
| 9 | 配置方式 | CLI 参数 > 环境变量 > 默认；启动时解析一次 |
| 10 | 估算策略 | 本地估算先行；实际 usage 仅事后校准 |

## 5. 引用

- FirstCoder 拆解：`docs/reference/firstcoder-architecture.md`
- M6 产品决策：见上方第 4 节（本仓库对话决策记录）
- 开发治理硬门禁：`docs/10-development-governance.md`
