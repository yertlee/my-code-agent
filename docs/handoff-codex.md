# 交接文档 · coding-agent 参照 FirstCoder 翻译式重写

> 写给 Codex 的接续者。本文档自包含:读完即可接手 Stage 4/5,不必回溯历史对话。
> 最后更新:2026-08-27（Stage 3 完成后暂停）

---

## 1. 项目是什么

`coding-agent` 是一个本地 CLI coding agent,以"可读、可学习、不黑盒"为核心定位。
当前定位已转向:**参照 FirstCoder 骨架,做完整的翻译式重写**,不再是单纯的"可读性实验"。

- 入口:`uv run agent`（`src/coding_agent/cli.py`）
- 技术栈:Python 3.12,uv 管理,依赖仅 4 个 runtime（openai / prompt-toolkit / pydantic / rich）
- 产品源码预算:v0.1.0 ≤ 8,000 行;AgentLoop ≤ 500 行;Kernel ≤ 2,000 行
- 完整测试:当前 **100 项全绿**（`uv run pytest`）

## 2. 方向转变（重要背景）

**旧方向**（M1-M5 已完成）:一条 `CLI → AgentApplication → AgentLoop → Provider/Tool → TurnResult`
主线,靠窄 contract 插件化,做"可通读"的最小闭环。M1 Provider Loop、M2 Tool Loop、
M3 Application Kernel、M4 编码 preset、M5 Durable Session,全部完成并 closeout。

**新方向**（现在）:用户明确"想做一个 firstcode"。FirstCoder 是朋友（KomorGiaoGiao）的仓库
（GitHub: KomorGiaoGiao/FirstCoder）,已获复用许可。决策为:**以当前仓库为底、按 FirstCoder
架构骨架重搭、核心模块翻译式重写**。即:
- **不推翻当前仓库**（providers/permissions/runtime/workspace/tools 已达标,保留）
- **参照 FirstCoder 的架构**,但**翻译式重写**（复用思想,不 copy 代码、不整包搬）
- 关键架构不变式:**Session 事实账本（AgentMessage/MessagePart）↔ 每轮投影（ContextBuilder）分离**,
  压缩只改投影视图、绝不篡改事实

## 3. 关键文档索引（必读）

| 文档 | 内容 |
|---|---|
| `docs/reference/firstcoder-architecture.md` | FirstCoder 完整拆解（2,534 行,200 文件零遗漏,章节号 FC:x） |
| `docs/reference/rewrite-plan.md` | 对齐计划:三层判断 + 目标骨架 + 5 个 Stage + M6 十项产品决策 |
| `docs/10-development-governance.md` | 硬性治理门禁（行数/模块/依赖/测试） |
| `docs/00-product-charter.md` | 产品章程（原始定位） |
| `PROJECT_STATUS.md` | 项目状态总览 |

## 4. 已完成内容（当前代码基线）

### Stage 1 · Session 事实层升级 ✅
- 新增 `src/coding_agent/session/facts.py`:事实账本模型
  - `AgentMessage`（id/session_id/turn_id/role/parts/created_at/metadata）
  - `MessagePart`（id/message_id/kind/content/metadata）
  - `PartKind`:text / tool_call / tool_result
  - 构造助手 `user_message` / `assistant_message` / `tool_result_message`
  - `tool_result_message` 把 `ok`/`tool_call_id`/`tool_name`/`truncated` + ToolResult 自带 metadata
    合并进 part metadata（**这是 Stage 4 lifecycle 分类的原料**）
- `session/models.py`:`SessionSnapshot.messages` 改为 `tuple[AgentMessage, ...]`
- `session/store.py` / `session/jsonl.py`:事实化;JSONL 使用当前 schema（每条事实消息都带 turn_id）
- `session/codec.py`:删除基于 ModelMessage 的 `message_from`
- `context/builder.py`:`facts_to_model_messages(snapshot) -> tuple[ModelMessage, ...]` ——
  **事实→provider 消息的唯一投影点**
- `agent/loop.py`:assistant/tool_result 落库改走 facts 构造助手
- 新增 `tests/unit/test_facts.py`（5 项）;测试 56 全绿

### Stage 2 · Provider seam 双形态对齐 ✅
- `protocol/models.py`:新增 `ChatResponse`（content/reasoning_content/tool_calls/finish_reason/usage/error）;
  `ProviderError` 增加 `requires_compaction: bool = False`（**M1 的 ProviderErrorKind 枚举值未动**）
- `providers/base.py`:`ChatProvider` 协议 = `complete(request) -> ChatResponse` +
  `stream(request) -> AsyncIterator[ModelStreamEvent]` + `aclose()`
- `providers/fake.py` / `providers/openai_compatible.py`:补 `complete`;complete/stream 共享解析逻辑
- `classify_openai_error`:PROMPT_TOO_LONG → `requires_compaction=True`
- `agent/loop.py`:`_run_loop` 主路径改走 `provider.complete(request)`;保留流式分支
  （`stream_output` 布尔开关,默认 False）;共享 `_process_completion` 结算
- 测试 64 全绿;AgentLoop 压回 500 行

### Stage 3 · Context 投影管线 ✅
- 新增 `src/coding_agent/context/estimator.py`:TokenEstimator
  - `estimate_text_tokens = max(1, (len+3)//4)`（字符÷4 近似,**不绑 tokenizer**）
  - `estimate_message_tokens` / `estimate_tool_definition_tokens` / `estimate_snapshot_tokens`
- 新增 `src/coding_agent/context/budget.py`:
  - `ContextBudget`（frozen）:context_window/output_reserve/input_capacity/fixed_tokens/
    history_tokens/input_tokens/high_watermark/low_watermark/source
  - 默认 `DEFAULT_CONTEXT_WINDOW=32_768`、`DEFAULT_OUTPUT_RESERVE=4_096`
  - 水位:`WATERMARK_L1=0.70`、`WATERMARK_L2=0.85`（相对 input_capacity）;
    不做 FC 的 0.95 折扣（窗口即输入预算,用户可预期）
  - `ContextProjectionLevel`:L0（<70% 充足）/ L1（70%-85% 候选）/ L2（≥85% 需压缩）
  - `ContextProjection`（frozen）:session_id/level/budget/messages_projected/facts_count/
    needs_compaction/suggested_level + `to_event_payload()`
- `build_context_budget(...)`:校验 window/reserve 正数、预留后仍有输入容量、low<high
- `context/builder.py`:新增 `BudgetedContextBuilder`（默认构造器）,**保留 `BasicContextBuilder`
  与 `facts_to_model_messages` 唯一投影点**;`build` 内算 budget → 判水位 → 暴露 `last_projection`
- `agent/loop_helpers.py`:`_TurnState` + 4 个纯函数从 loop.py 拆出（维持 AgentLoop ≤500 行）
- `runtime/events.py`:新增 `RuntimeEventKind.CONTEXT_PROJECTED`
- `agent/loop.py`:`_run_loop` 在 `build()` 后 emit `CONTEXT_PROJECTED`（只记录,不触发压缩）
- `config.py` / `app/factory.py`:`CODING_AGENT_CONTEXT_WINDOW` 环境变量,启动时解析一次;
  `build_application` 默认构造 `BudgetedContextBuilder`（保留 `context_builder` 注入覆盖）
- 新增 `tests/unit/test_context_budget.py` / `test_context_projection.py` / `test_config.py`（26 项）;
  **测试 90 全绿**

### Stage 4 · Context 压缩语义 ✅
- 新增 `context/compaction.py`：纯确定性的 ToolResultLifecycle 分类与 L1/L2 投影压缩。
- L1：单条工具结果限制为输入预算的 20%，保留头尾和明确省略标记。
- L2：以 `turn_id` 为完整工作回合边界淘汰历史，当前任务与最近修改后的证据区不拆分。
- L3：投影仍超过输入容量时，loop 在调用 provider 前以
  `context_budget_exceeded` 停止。
- 压缩只构造临时事实视图；Session facts 与 JSONL 始终保持原样。
- 新增 `tests/unit/test_context_compaction.py`；**测试 96 全绿**。

### 当前代码规模（Stage 4 后）
- AgentLoop 422/500 行、产品源码 4,320/8,000 行
- 100 项测试全绿,ruff / basedpyright 通过,无新增 runtime dependency

## 5. 当前状态与接缝（接手点）

**当前接手点**:Stage 5 已完成；Context 主线从事实账本、预算、压缩到 CLI/JSON 可观测性已闭环。

**后续扩展接缝**:
- `BudgetedContextBuilder.last_projection: ContextProjection | None`
  （含 level / needs_compaction / suggested_level / budget）
- loop 每轮 `build()` 后已发 `RuntimeEventKind.CONTEXT_PROJECTED` 事件
- `ContextProjection.to_event_payload()` 已包含压缩数、淘汰轮次数与预算超限状态，可直接供
  CLI 和 JSON 渲染消费

## 6. 待办（剩余 Stage）

### Stage 5 · CLI / 渲染 / 可观测性 + 测试 ✅
- `CONTEXT_PROJECTED` 的预算与压缩摘要进入 `TurnResult` / JSON；普通 CLI 与交互渲染仅在
  压缩或超限发生时输出 Context 行
- `--context-window` 覆盖环境变量，并在启动时传入 `BudgetedContextBuilder`
- CLI JSON、配置优先级和超限终端提示均有测试覆盖；**测试 100 全绿**

### 可选后续（非本交接范围）
- 对齐 FirstCoder 的 checkpoint/archive/LLM 摘要、MCP、skills、规划层、子代理等
  （见 rewrite-plan 第 17 章与 firstcoder-architecture 附录 B）——**需用户确认是否要做**

## 7. M6 十项产品决策（Stage 4/5 必须遵守）

| # | 决策 | 结论 |
|---|---|---|
| 1 | 默认窗口 | 32k（`CODING_AGENT_CONTEXT_WINDOW` 可覆盖） |
| 2 | 输出预留 | 4k 常量,溢出边际给输入 |
| 3 | 压缩目标 | 当前任务 > 工具证据链 > 可重建历史 |
| 4 | L1 规则 | 单条 ToolResult 为单位;超长判定用估算器;头尾保留 + 显式省略 |
| 5 | L2 单位 | 完整工作轮次,跨 tool_calls 成批保留;用户消息为边界 |
| 6 | 核心保护区 | 当前任务 / pending / 最近修改验证 / 工具配对,永不拆散 |
| 7 | L3 行为 | 明确停止 `context_budget_exceeded`,不做自动模型摘要 |
| 8 | 可观察性 | CLI 提示 + JSON 摘要 + `CONTEXT_PROJECTED` 事件 |
| 9 | 配置方式 | CLI 参数 > 环境变量 > 默认;启动时解析一次 |
| 10 | 估算策略 | 本地估算先行;实际 usage 仅事后校准 |

## 8. 硬性约束（每次改动都要守）

- **行数预算**:AgentLoop ≤ 500、Kernel ≤ 2,000、产品源码 ≤ 8,000。触线需说明并裁减。
- **不新增 runtime dependency**（需要新依赖 = ADR + 用户批准）。
- **单一 ContextBuilder seam**:`facts_to_model_messages` 是事实→provider 消息唯一投影点;
  `BudgetedContextBuilder` 必须满足 `ContextBuilder` 协议（`build(model, snapshot, tools) -> ModelRequest`,
  loop 签名零改动）。
- **事实层不可变**:压缩/裁剪只影响投影视图,绝不修改 `AgentMessage/MessagePart` 事实或 JSONL 日志。
- **冻结类型不改**:`ModelRequest/ModelMessage/ModelStreamEvent/TextDelta/ReasoningDelta/ResponseCompleted`
  是 M1 冻结的 provider 侧类型;`ProviderErrorKind` 枚举值不新增不改。
- **每 Stage 测试全绿**（`uv run pytest`）、ruff / basedpyright 通过、编码风格与仓库一致
  （中文 docstring、类型标注、slots dataclass）。

## 9. 工作方式（省 token,重要）

- **大规模读写交给后台子代理**:读大仓库/写大文件/大迁移,交给 `general-purpose` 子代理
  （有读写能力）;让它 **Write 落盘、只回文件路径 + 覆盖清单 + 章节索引**,不让全文回流主上下文。
- **主流程只做**:验收（抽查关键产出 + 跑测试）、定边界、写决策文档、更新 PROJECT_STATUS 与记忆。
- **子代理 prompt 模板**:背景必读 → 现状 → 核心目标 → 具体任务编号 → 硬性约束 → 最终回复格式
  （改动清单 + 要点 + 测试结果 + 触线说明）。
- **用户不要留技术债**:"要做就直接做完,别再拖"——决策前先问清边界,别做半截。
- **每完成一个 Stage**:更新 `PROJECT_STATUS.md`、`docs/reference/rewrite-plan.md` 的进度标记。

## 10. 当前 git 状态

- 分支 `main`,未 commit Stage 1-3（子代理按约定不 commit,由主流程统一处理）。
- 接手第一步建议:先 `uv run pytest` 确认 100 项全绿,再 `git status` 看当前工作区,
  然后从 Stage 4 开始。
- 项目文档更新规范:每个 Stage closeout 需同步 PROJECT_STATUS.md 与对应 plans 文档。
