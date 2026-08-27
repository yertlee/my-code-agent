# FirstCoder 仓库完整架构拆解

> 面向「翻译式重写」的参考实现架构说明书。
> 仓库根目录：`D:\Myproject\agent\.tmp-firstcoder-inspect\firstcoder`
> 规模：约 29.7k 行 Python、197 个 `.py` 文件、200 个非忽略文件（另含 `tui.tcss` 与两个 prompt md）。
> 本文档只读拆解，未修改任何源文件。

---

## 0. 如何阅读本文档

### 0.1 文档组织方式

本文档是「翻译式重写」的蓝图。章节顺序即重写时建议的阅读/实现顺序：

- **第 1 章**：总览。先看模块地图、依赖方向、端到端主流程与设计主题索引，建立全局坐标系。
- **第 2~15 章**：按包逐层拆解。每章覆盖一个包，每个文件（或高度内聚的文件组）用五要素模板拆解。
- **第 16 章**：横切关注点。把分散在多个包里的同一主题（消息模型、持久化、压缩、权限、可观测性……）横向打通。
- **第 17 章**：翻译式重写评估表 + 建议的重写优先级。
- **附录 A**：文件覆盖清单（每个文件映射到章节，保证零遗漏）。
- **附录 B**：重点精读文件清单及拆解要点。

### 0.2 每章/每个文件的模板

对每个文件（或高度内聚的文件组）按下述五要素撰写：

1. **职责**：一句话定位。
2. **对外 API**：导出的关键类/函数，带签名、关键参数、返回类型；数据类列出全部字段。
3. **核心流程（伪代码）**：该模块最关键 1~3 条路径的伪代码。
4. **与相邻模块的关系**：依赖了谁、被谁依赖；数据在模块间如何流动。
5. **为什么这么设计（设计原理）**：解决什么问题、放这一层的原因、取舍、隐藏的坑、重写时哪部分核心必须保留、哪部分可简化。
6. **重写标注**：`【保留】` `【简化】` `【必须改】` `【暂缓】` 四选一，附一句理由。

### 0.3 标注约定

- **重点精读文件**：在文件名前标 `📌`。这些文件逐行理解、拆解最细（见附录 B）。
- **伪代码**：用 ``` 代码块，只画主干，忽略防御性分支。
- **重写标注**的含义：
  - `【保留】`：核心语义正确，翻译时几乎照搬。
  - `【简化】`：可以砍掉部分外围逻辑，但核心保留。
  - `【必须改】`：存在 FirstCoder 特有假设（如 Terminal-Bench / benchmark 协议 / Yuren 厂商），重写时需替换或移除。
  - `【暂缓】`：外围/可选能力，重写时可后置。
- 文中的「token 估算」都是 FirstCoder 自己的近似算法（`estimate_text_tokens`，字符数÷4），不是真实 tokenizer。

---

## 1. 总览

### 1.1 仓库构成

| 包 | 文件数 | 行数 | 定位 |
|---|---|---|---|
| `context/`（根） | 28 | ~5,050 | 上下文系统核心：事实模型、事件日志、投影、L1-L4 压缩、checkpoint、archive、task boundary。**最大的模块** |
| `context/content/` | 10 | ~1,250 | L2 内容路由压缩器（diff/build/json/code/html/search/plain） |
| `context/prompts/` | 2 | ~134 | 系统提示词正文（交互版 / benchmark 版） |
| `agent/` | 21 | ~5,870 | Agent 主循环、会话运行时、工具执行、后台任务、子代理、benchmark 门禁 |
| `tools/` | 44 | ~4,400 | 全部工具（文件/搜索/执行/网络/规划/权限/控制面）与注册表 |
| `app/` | 26 + `tui.tcss` | ~4,500 + 181 | Textual TUI 应用层 |
| `providers/` | 9 | ~1,810 | Provider 抽象与实现（OpenAI-compatible / Anthropic） |
| `session/` | 11 | ~1,210 | 用户可见 session 能力：catalog、resume、fork、share、transcript |
| `mcp/` | 8 | ~1,010 | MCP 配置/传输/管理器/工具适配 |
| `permissions/` | 5 | ~830 | 权限策略、grants、确认决策 |
| `planning/` | 6 | ~800 | 任务规划领域模型与 reducer |
| `input/` | 3 | ~570 | 附件、剪贴板、粘贴解析 |
| `skills/` | 6 | ~510 | 技能发现、加载、会话审计 |
| `config/` | 3 | ~490 | TOML 配置加载与模型目录 |
| `utils/` | 10 | ~670 | 沙箱、子进程、文本、JSON、schema 工具 |
| `runtime/` | 3 | ~180 | 跨层原语：取消令牌、用户输入请求 |
| 根 + `cli.py` | 3 | ~600 | 入口壳与命令行 |

> 行数为 `wc -l` 近似。`context/content/` 是 L2 内容路由压缩器集合，`app/` 是 TUI 渲染层，二者都偏「独立小算法」。

### 1.2 分层与依赖方向

依赖方向（import 方向）大致为「下三层不依赖上层」：

```
cli.py / app/ (TUI + factory)          ← 最外层，装配一切
   │
agent/ (loop, session, tool_execution) ← 编排层：串起 provider / context / tools / permissions
   │
context/  session/  providers/  tools/  permissions/  planning/  skills/  mcp/
   │        │          │          │          │            │         │        │
   └────────┴───┬──────┴─────┬────┘          │            │         │        │
              runtime/       └──►  utils/    └────────────┴─────────┴────────┘
              (取消/用户输入)    (沙箱/子进程/文本/JSON)
```

具体约束（从代码 import 逆推）：

- **`runtime/` 是全仓最底层的共享包**：`cancellation`（取消令牌）、`user_input`（UserInputRequest）。`agent`、`tools`、`permissions`、`utils` 都依赖它；它不依赖任何上层。
- **`utils/` 依赖 `runtime/`**（子进程要读取消令牌），但 `utils/sandbox_access`、`utils/text` 等是纯工具，被所有层使用。
- **`context/` 依赖 `runtime/`、`planning/`、`utils/`**，不依赖 agent；但 `context/manager.py` 的 `ContextManagerLike` 是 `agent/ports.py` 引用它的协议（方向是 agent→context）。
- **`providers/` 依赖 `utils/json_utils`、`utils/schema`**，不依赖 agent/context。`agent` 只依赖 `providers.base.ChatProvider` 抽象。
- **`permissions/` 依赖 `runtime/user_input`**，被 `agent`、`tools` 依赖。
- **`planning/` 是纯领域包**：不 import agent/runtime/context 任何东西，`context/models.py` 引用 `planning.models.TaskPlan`（context→planning）。
- **`tools/` 依赖 `runtime/`、`utils/`、`providers/types`、`permissions/types`**，大部分工具不依赖 agent。例外：`tools/processes.py` 依赖 `agent/processes.py`；`tools/delegate.py` 依赖 `agent/subagent.py`。`tools/__init__.py` 用惰性 `__getattr__` 避免包级循环。
- **`session/` 依赖 `context/`（store/writer）与 `agent/session`（仅 type-checking）**。
- **`app/` 依赖除 `cli.py` 外的一切**：它是装配根。`app/factory.py` 是唯一知道「如何把 provider + context_manager + tools + MCP + session services 拼成一个 TUI」的地方。
- **`cli.py` 依赖 `app/factory`**。

**核心 spine（主线必需，重写先写）**：
`config` → `providers` → `runtime` → `context`（models/store/writer/context_builder/manager/compaction）→ `permissions` → `tools`（registry + 少量内置工具）→ `agent`（session/loop/tool_execution）→ `session`（bootstrap/catalog/resume）→ `app/factory` → `cli`。

**外围可延后**：
`mcp/`、`skills/`、`input/`（附件/剪贴板）、`app` 的渲染细节（welcome、topbar 主题、picker）、`planning/`、`context/content/*`（L2 路由压缩器）、`agent` 的 benchmark 门禁（execution_evidence / stagnation / completion gate）、`agent/subagent + worktree + delegate`。

### 1.3 端到端主流程（`python -m firstcoder` → 一个完整 turn）

```
main(argv)
  ├─ build_parser()：子命令 config/mcp + 通用参数（--project/--session-id/--message/--tui/...）
  ├─ config 命令 → run_config_command（path/show/init）
  ├─ mcp 命令 → run_mcp_command（add/list/remove，写全局 TOML）
  ├─ 单消息 / REPL / TUI 三分支：
  │     ├─ --tui 或 stdin 非 tty → create_cli_app(config).run()   # Textual App
  │     ├─ --interactive → create_cli_app + run_repl()（行式 REPL）
  │     └─ 单消息 → run_single_turn(config)
  │             → create_cli_app()（装配 AgentChatRunner）
  │             → chat_runner.run_user_turn(message) → asyncio.run(arun_user_turn)
  │             → AgentLoop.run_user_turn（见下）→ 打印 response.content
  │     benchmark 变体：run_benchmark_turn() → 设 BYPASS 权限、关 prewrite review、
  │                     set_benchmark_task(message)、swe_lite 限额 → run_user_turn
```

一个 turn（`AgentLoop.run_user_turn` → `_run_user_turn_sync_impl`）：

```
1. 若 session.pending_permission_execution 非空 → 直接返回 WAITING_FOR_USER_INPUT
2. _validate_attachments（图片必须 provider 支持 vision）
3. _begin_turn()：重置 tool_rounds、execution_evidence、stagnation_guard、turn_telemetry
4. _repair_interrupted_tool_calls_before_provider_request()：修复历史尾部未闭合 tool_call
5. append_user_message(content, attachments) → SessionEventWriter 写 user_message 事件
   （writer.current_turn += 1；parts 附 created_turn/turn_id）
6. 任务边界初始化/分类：
   - _initialize_active_task_if_missing(basis_message_id)：若 active_task_hash 为空，
     直接用该消息 id 生成稳定 hash 并写 task_boundary_observed 事件
   - 否则 _classify_task_boundary()：调隐藏 LLM 分类器（TaskBoundaryClassifier，
     3 次尝试解析 {"decision","basis_message_id"}），把结果写入 TaskBoundaryService
7. _run_tool_loop_interactive(_complete_once_with_recovery)  —— 工具循环
   while True:
     a. _complete_once_with_recovery(tool_choice="auto")
          = _prepare_main_provider_request → provider.complete(ChatRequest)
            · repair interrupted tail
            · append pending guidance（guidance_provider 排空）
            · append background notifications（drain 完成的后台任务 → 独立 user 消息）
            · _provider_tool_definitions()：按 runtime_capabilities / MCP 激活集过滤 schema
            · rebuild_view() → ContextBuilder.build_provider_messages(view, system_prefix, ...)
            · build_context_budget(messages, tools, context_window, max_tokens)
            · context_manager.compact_if_needed(ContextCompactRequest)   ← 自动压缩触发点
            · 构造 PreparedMainRequest（request_id + projection_fingerprint + tool_result_part_ids）
          · ProviderError 处理：retryable → 指数退避重试；requires_compaction → 触发
            PROMPT_TOO_LONG 压缩后重试一次
     b. response = _drop_unsupported_tool_calls(...)：supports_tools=False 时丢弃 tool_calls
     c. while response.tool_calls:
          - 检查 max_tool_rounds（超限 → _tool_round_limit_response）
          - session.append_assistant_response(response)：写 assistant_message 事件
            （文本 part + tool_call parts，tool_call metadata 存 tool_call_id/tool_name/arguments）
          - tool_executor.execute_interactive(response.tool_calls)
            · 逐个工具：validate（MCP 激活/运行时可见性/stagnation）→ 权限预检
              （DENY→denied 结果；ASK→存 pending_permission_execution，返回 pending_input 暂停）
            · 后台控制字段剥离（run_in_background/label/task_id）
            · 只读工具同批并行（ThreadPoolExecutor）
            · 每个结果 session.append_tool_result(...) → tool_result 事件
              （append_tool_result 幂等：_tool_result_message_ids 去重）
            · task_boundary 结果触发 task_hash_changed → _compact_after_task_hash_changed()
          - execution.pending_input 非空 → 返回 WAITING_FOR_USER_INPUT（UI 显示确认）
          - tool_rounds += 1；再次 complete_once()
     d. 无 tool_calls 后：
          - _run_task_plan_reconciliation_if_needed：TaskPlan 有未完成任务 →
            附加一条 system reconciliation 指令再问一次
          - _run_completion_gate_if_needed：benchmark 模式，ExecutionEvidence 检测
            未验证修改/失败验证/后台未结束 → 注入 gate 指令再问一次（最多 2 次）
8. _complete_turn(response)：
   - session.append_assistant_response(response)（最终文本）
   - 按 finish_reason 归类 status（completed/interrupted/limited/errored）
   - _persist_turn_telemetry → agent_turn_telemetry 事件
   - 返回 AgentTurnResult
9. 异常路径：_persist_errored_turn(exc) 写 telemetry；AgentCancelledError →
   _append_interrupted_tool_results() 给未闭合 tool_call 补 interrupted 结果
```

### 1.4 关键设计主题索引

| 主题 | 核心章节 | 一句话 |
|---|---|---|
| 消息事实模型 vs provider 消息 | 4、6、16.1 | `AgentMessage/MessagePart` 是持久化事实账本；`ChatMessage` 是每次投影出来的请求格式，二者分离 |
| Session 持久化与恢复 | 4、9（store/writer/checkpoint）、session/ | append-only JSONL + 事件重放 + checkpoint 投影 |
| Context 投影管线 | 9（context_builder/compaction/manager） | budget → lifecycle 分类 → L1-L3 程序化压缩 → L4 LLM 摘要 → provider messages |
| 工具执行、证据与结算 | 5（tool_flow/tool_execution/tool_settlement）、16.4 | tool_call→tool_result 原子配对；权限暂停；后台占位；interrupted 修补 |
| 错误处理 | 5（loop 的 retry/limit/stagnation）、16.5 | provider 错误分类、重试退避、prompt-too-long 压缩恢复、停滞检测 |
| 权限与安全 | 7、16.6 | 纯函数策略 + grant 覆盖 + ASK 暂停；工具声明驱动 |
| 可观测性 | 5（telemetry）、9（events/inspector）、16.7 | 结构化计数写 JSONL；TUI 实时事件 |
| TUI 状态管理与渲染 | 14、16.8 | TuiTranscript 增量模型 + stream/tool 事件 handler |
| 多代理/后台/子代理 | 5（background/subagent/worktree）、16.9 | ThreadPoolExecutor + 占位结果 + worktree 隔离 |

---

## 2. 入口与 CLI（根目录 + cli.py）

### 📌 `__init__.py`
- **职责**：包 docstring 占位，无逻辑。
- **对外 API**：无。
- **核心流程**：无。
- **相邻关系**：无。
- **设计原理**：空文件只是包标记。
- **重写标注**：`【保留】`（照抄空文件）。

### 📌 `__main__.py`
- **职责**：`python -m firstcoder` 入口，委托 `cli.main`。
- **对外 API**：`raise SystemExit(main())`。
- **核心流程**：`main()` → `SystemExit`。
- **相邻关系**：依赖 `firstcoder.cli`。
- **设计原理**：极薄壳，把 `-m` 与 `python firstcoder/cli.py` 统一到同一个 `main`。
- **重写标注**：`【保留】`。

### 📌 `cli.py`（597 行）
- **职责**：命令行解析与三种运行模式（单消息 / REPL / TUI）的分发，外加 `config`、`mcp` 子命令。
- **对外 API**：
  - `CliConfig`（frozen dataclass）：`project_root, data_root, session_id, message, model_spec, max_tool_rounds, max_turn_seconds, reasoning_effort, benchmark, resume_session, attachments`。
  - `main(argv=None, *, runner=None, stdin_text=None) -> int`。
  - `run_single_turn(config) -> str`、`run_benchmark_turn(config) -> str`。
  - `create_cli_app(config)`：装配 `AgentRuntimeCapabilities` + `create_firstcoder_app`，并应用 limits / reasoning_effort。
  - `run_repl(chat_runner, lines, *, auto_approve)`：行式 REPL，处理权限确认输入。
- **核心流程**：
```
build_parser()
if config 子命令 → run_config_command
if mcp 子命令 → run_mcp_command
if --tui 或 (无 --message 且 stdin 是 tty 且非 --interactive) → create_cli_app().run()
if --interactive → create_cli_app + run_repl
否则单消息 → read_message(--message 或 stdin) → create_cli_app → run_user_turn → print(content)
```
- **相邻关系**：依赖 `config`、`app/factory`、`app/ports`、`agent/loop_limits`、`agent/runtime_capabilities`、`input/attachments`、`mcp/config_store`、`permissions/types`。
- **设计原理**：
  - 用 `CliRunner = Callable[[CliConfig], str]` 作为可注入边界，测试不需要真实运行 app。
  - `--benchmark` 走独立 `run_benchmark_turn`，在 CLI 层设置 BYPASS 权限与 benchmark 任务，避免污染普通路径。
  - `--message` 缺省时读 stdin，且「stdin 非 tty」自动进 TUI（`sys.stdin.isatty()` 判断）。
  - REPL 的权限确认做了文本别名映射（`1/y/allow_once`…），并支持 `reject: feedback`。
- **隐藏的坑**：`--attachment` 仅限单消息模式；`--auto-approve` 只在 REPL 生效；`_benchmark_limits` 用 `swe_lite` 基数并保留 40 次 provider 调用余量。
- **重写标注**：`【保留】`（入口壳可整体照搬；去掉 benchmark 分支可再简化）。

---

## 3. 配置层（config/）

### `config/__init__.py`
- **职责**：配置层公共入口，导出 `AppConfig`、`load_config`、Model Catalog 类型。
- **对外 API**：`__all__` 列出 `AppConfig, load_config, ModelCatalog, ModelCatalogError, ModelProfile, ModelRequestOptions, ProviderProfile`。
- **设计原理**：所有上层只 import `config` 包级名字，不深入内部。
- **重写标注**：`【保留】`。

### 📌 `config/settings.py`（223 行）
- **职责**：从全局 TOML、项目 TOML、`.env`、环境变量加载应用配置，生成不可变 `AppConfig`。
- **对外 API**：
  - `AppConfig`（frozen dataclass）：字段 `env, project_config, global_config, project_config_path, global_config_path`。方法：`get_env(name, default)`、`get_provider_bool(name, *, env, default, provider_name)`、`get_config_value(name, *, default)`、`mcp_config()`（按名合并，项目覆盖全局）、`model_catalog()`、`loaded_config_paths`。
  - `load_config(*, project_root=None, env=None) -> AppConfig`。
  - `default_global_config_path() -> Path`、`project_config_path(project_root) -> Path`。
  - `render_default_config() -> str`（默认 TOML 模板）。
- **核心流程**：
```
load_dotenv() → env_snapshot = os.environ
global_path = ~/.config/firstcoder/config.toml（XDG_CONFIG_HOME 优先）
project_path = <root>/firstcoder.toml
global_config = tomllib 读 global；project_config = tomllib 读 project
返回 AppConfig(...)
```
- **相邻关系**：依赖 `config/models.build_model_catalog`；被 `cli.py`、`app/factory.py`、`mcp/config.py` 依赖。
- **设计原理**：
  - provider 与模型选择只走 Model Catalog；旧的单 provider 环境变量不再参与选择（见 `models.py` 报错）。
  - `AppConfig` 是 provider factory 的唯一配置来源，隐藏「配置来自 TOML 还是环境」。
  - `get_provider_bool` 有明确优先级：env → project → global → default。
- **重写标注**：`【保留】`（配置层通用，可照搬；去掉 yurenapi 默认模板即可）。

### 📌 `config/models.py`（248 行）
- **职责**：多模型 Catalog 的领域模型与 TOML 解析，含严格校验。
- **对外 API**：
  - `ModelRequestOptions`（frozen）：`temperature, max_tokens, reasoning_effort, extra_body`。
  - `ProviderProfile`（frozen）：`id, type, base_url, api_key_env, parallel_tool_calls, streaming`。
  - `ModelProfile`（frozen）：`ref, provider_id, model_id, label, provider, request, context_window, vision`。
  - `ModelCatalog`（frozen）：`default_ref, profiles`；方法 `list() / get(ref) / require(ref)`。
  - `build_model_catalog(global_config=None, project_config=None) -> ModelCatalog`。
  - `ModelCatalogError(ValueError)`。
- **核心流程**：
```
providers_raw = deep_merge(global.providers, project.providers)
models_raw = deep_merge(global.models, project.models)
if not models_raw and 有旧 model/provider 字段 → 抛迁移错误
每个 models 条目：ref 必须 "provider/model"，provider 必须已定义
  解析 label/request/context_window/vision；校验 max_tokens < context_window*0.95
default_ref = project.default_model or global.default_model；必须存在于 profiles
返回 ModelCatalog
```
- **相邻关系**：依赖 `context/budget_defaults`（DEFAULT_CONTEXT_WINDOW=200_000, DEFAULT_OUTPUT_RESERVE=4_096）。被 `config/settings`、`providers/factory`、`app/factory` 依赖。
- **设计原理**：
  - 冻结 dataclass + 深拷贝，保证目录不可变。
  - `_RESERVED_REQUEST_EXTRA_BODY_FIELDS` 禁止 `extra_body` 覆盖 `model/messages/tools/stream/...` 等核心字段，防止厂商参数悄悄替换请求语义。
  - `_validate_context_capacity` 在配置期就阻止「输出预留吃掉 95% 窗口」的坏配置。
- **重写标注**：`【保留】`。

---

## 4. 消息模型与 Session 事实（context/models.py + session/ 全部）

### 📌 `context/models.py`（112 行）
- **职责**：FirstCoder 内部会话事实模型（长期事实账本），与 provider 请求格式解耦。
- **对外 API**：
  - `MessageRole = Literal["user","assistant","tool","system_meta"]`。
  - `PartKind = Literal["text","tool_call","tool_result","checkpoint_summary","compaction_event_ref","archive_placeholder"]`。
  - `utc_now_iso() -> str`：稳定 UTC ISO（微秒置 0，`Z` 后缀）。
  - `MessagePart`（slots dataclass）：字段 `id, message_id, kind, content, metadata`；方法 `from_dict/to_dict`。
  - `AgentMessage`（slots dataclass）：字段 `id, session_id, role, parts, created_at, metadata`；方法 `from_dict/to_dict`。
  - `latest_user_message_id(messages) -> str | None`。
  - `SessionView`（slots dataclass）：字段 `session_id, messages, checkpoints, metadata, task_plan`。**注意：它是「从事件日志重放得到的当前视图」，不是持久化对象。**
- **核心流程**：无业务逻辑，纯数据容器 + dict 序列化。
- **相邻关系**：依赖 `planning.models.TaskPlan`（TYPE_CHECKING 下依赖 `context.checkpoint.Checkpoint`）。被 `store/writer/context_builder/compaction/llm_compact` 等几乎所有 context 文件依赖。
- **设计原理**：
  - 这是整个仓库最重要的一层分离：**持久化事实（AgentMessage/MessagePart）≠ provider 请求格式（ChatMessage）**。context_builder 每轮把 view 投影成 ChatMessage。
  - `PartKind` 里的 `checkpoint_summary / compaction_event_ref / archive_placeholder` 是压缩产物，说明事实账本允许「非自然语言」的 part。
  - `metadata` 是 `dict[str, Any]`，承担大量运行时信息（tool_call_id、arguments、created_turn、task_hash、compaction_state、archive_id…），是设计上的「脏口袋」。
- **重写标注**：`【保留】`（核心模型，照搬）。

### `session/models.py`（93 行）
- **职责**：session 层用户可见数据模型（resume 列表、分享、只读 transcript），不替代 `SessionView`。
- **对外 API**：
  - `SessionStatus = Literal["ok","empty","corrupt"]`、`ArchiveMode = Literal["placeholder","preview_only"]`。
  - `SessionRecord`：`session_id, title, created_at, updated_at, workspace, provider, model, message_count, user_turn_count, checkpoint_count, archive_count, latest_user_input, latest_assistant_output, latest_checkpoint_id, status, error, metadata`。
  - `RedactionOptions`：`redact_paths, redact_secrets`。
  - `ShareOptions`：`include_event_ids, include_compaction_metadata, include_tool_calls, include_tool_results, max_tool_result_chars, redact_paths, redact_secrets, archive_mode`。
  - `TranscriptEntry`：`role, title, content, message_id, metadata`。
  - `Transcript`：`session, entries`。
  - `ResumeResult`：`session, record`。
- **设计原理**：`SessionRecord` 是 catalog 扫描 JSONL 得到的摘要；`ResumeResult.session` 是 `AgentSession`（TYPE_CHECKING 引用，避免循环）。
- **重写标注**：`【保留】`。

### `session/errors.py`（37 行）
- **职责**：session 层异常类型（`SessionError` 及其 `NotFound/InvalidId/Empty/Corrupt/UnsupportedSchema` 子类）。
- **设计原理**：不让 TUI 看到底层 JSONL 解析细节。
- **重写标注**：`【保留】`。

### `session/redaction.py`（48 行）
- **职责**：分享文本脱敏（secret 赋值、JSON secret、Windows/POSIX 路径）。
- **对外 API**：`redact_text(text, options) -> str`。
- **设计原理**：第一版保守规则，不做完整 DLP；`[REDACTED_SECRET]` / `[REDACTED_PATH]` 占位。
- **重写标注**：`【简化】`（规则可后置）。

### `session/catalog.py`（235 行）
- **职责**：只读 session catalog，从 `.firstcoder/sessions/*.jsonl` 派生 resume 列表。
- **对外 API**：
  - `SessionCatalog(root)`：`list_sessions() -> list[SessionRecord]`、`get_session(session_id)`、`exists(session_id)`。
  - `record_from_path(path) -> SessionRecord`。
  - `build_record_from_events(*, session_id, events) -> SessionRecord`。
  - `is_safe_session_id(session_id) -> bool`（正则 `^[A-Za-z0-9_-]+$`）。
  - `require_usable_record(record)`（corrupt/empty 抛对应异常）。
- **核心流程**：
```
list_sessions → SessionIndex(root).list_records()
  → 读 session_index.json；缺失则 rebuild()（扫描 *.jsonl 逐个 record_from_path）
get_session → 校验 id → record_from_path(session_id.jsonl)
build_record_from_events：
  遍历 events：
    session_created/metadata_updated → merge metadata
    user/assistant/tool 事件 → message_count、preview、provider/model
    tool_result/compaction → archive_ids 收集
    checkpoint_created → checkpoint_count、latest_checkpoint_id
  title = metadata.title or latest_user_input or session_id
```
- **相邻关系**：依赖 `context/events`、`context/metadata`、`session/errors`、`session/index`。被 `app/factory`、`app/session_commands`、`session/resume/fork/transcript` 依赖。
- **设计原理**：catalog 是「只读派生层」，不修复 JSONL、不触发压缩、不构造 provider messages。单个损坏 session 被隔离为 `status="corrupt"` 而不是抛异常。
- **重写标注**：`【保留】`。

### 📌 `session/index.py`（235 行）
- **职责**：轻量 session 列表索引缓存（`session_index.json`），加速 `/sessions` 与 `/resume`。
- **对外 API**：`SessionIndex(root)`：`update_event(event)`、`list_records()`、`rebuild()`。
- **核心流程**：
```
update_event(event)：
  加全局 RLock；读 session_index.json
  events = 读该 session 的 JSONL；build_record_from_events → 写入 data["sessions"]
  （build 失败 → 记为 corrupt 记录，绝不让索引阻塞事件持久化）
list_records()：
  索引文件不存在 → rebuild()；存在 → _reconcile_missing_files()（补齐新 JSONL）
  按 session_sort_key（updated_at, session_id）倒序返回
```
- **相邻关系**：被 `JsonlSessionStore.append_event` 调用（**store 写入每个事件后同步更新索引**），被 `SessionCatalog.list_sessions` 调用。
- **设计原理**：索引是「读时懒重建 + 写时增量更新」的缓存；写临时文件再 `replace` 保证原子性。
- **隐藏的坑**：索引格式变化要升 `INDEX_VERSION`，否则整体重建。
- **重写标注**：`【简化】`（小规模可以直接每次扫目录；保留 `update_event` 钩子亦可）。

### `session/bootstrap.py`（73 行）
- **职责**：new / resume / fork / factory 共享的 AgentSession 装配点。
- **对外 API**：`SessionBootstrap(store, project_root, data_root=None, tools=None, tools_provider=None, sandbox_access=None)`；`create/resume/from_project(session_id)`；`permission_manager()`（用 `FilePermissionGrantStore(data_root/permissions.json)`）。
- **核心流程**：`create` = `AgentSession.create(store, session_id, agents_md=read_agents_md(project_root), skill_catalog=discover_all_skills(project_root), tools, permission_manager, sandbox_access)`。
- **设计原理**：把「项目规则、技能、权限、沙箱」的装配集中一处，UI/CLI 不需要知道细节。
- **重写标注**：`【保留】`。

### `session/new.py`（42 行）
- **职责**：`NewSessionService.create(title=None)` 创建新 session 并返回 `ResumeResult`。
- **重写标注**：`【保留】`。

### `session/resume.py`（109 行）
- **职责**：resume 编排入口，含 schema 校验。
- **对外 API**：`ResumeService.resume(session_id)`；`validate_session_schema(store, session_id)`。
- **核心流程**：
```
resume：
  validate_session_schema（id 安全、文件存在、第一条事件是 session_created、
    其 payload.context_event_schema_version 必须等于 CONTEXT_EVENT_SCHEMA_VERSION）
  record = require_usable_record(catalog.get_session)
  session = bootstrap.resume(session_id)
  session.restore_pending_permission_execution()   # 重建未完成权限确认
```
- **设计原理**：resume 的底层事实仍是完整 append-only event log；checkpoint 只影响下一轮投影，不是 resume 存储边界。schema 版本是硬边界（旧/缺版本/未来版本都拒绝）。
- **重写标注**：`【保留】`。

### `session/fork.py`（91 行）
- **职责**：把现有 session 事件日志复制成新 session 并 resume。
- **核心流程**：`validate → list_events → 逐条 _fork_event（重写 payload 里的 session_id，生成新 event id）→ append_event → 复制 archives 目录 → bootstrap.resume → restore_pending`。
- **设计原理**：fork 是「事件级浅拷贝 + archive 目录拷贝」，不改任何历史事实。
- **重写标注**：`【简化】`（可后置）。

### `session/share.py`（85 行）
- **职责**：只读 share 导出（Markdown transcript）。
- **对外 API**：`SessionShareService.export_markdown(session_id, *, output_path=None, options=None) -> Path`。
- **重写标注**：`【暂缓】`。

### `session/transcript.py`（223 行）
- **职责**：从 event log 派生只读 transcript。
- **核心流程**：遍历 events，`user_message/assistant_message/tool_result` → 消息条目；`checkpoint_created` → checkpoint 条目；`compaction_completed` → 可选压缩条目。工具结果默认不展开 archive 原文。
- **重写标注**：`【暂缓】`。

---

## 5. Agent 核心（agent/ 全部）

### 📌 `agent/loop.py`（1632 行）—— 重点精读
- **职责**：Agent 主循环，把「用户输入 → 上下文投影 → provider 调用 → 工具执行」串成一轮会话事务。刻意不混入具体工具/SDK/widget。
- **对外 API**：
  - `AgentLoop` 类。构造参数极多（见下），关键方法：
    - `async run_user_turn(content, *, attachments=None, streaming=False) -> AgentTurnResult`。
    - `async resume_with_user_input(request_id, answer, *, streaming=False) -> AgentTurnResult`。
    - `replace_cancellation_token(token)`、`clear_stream_events()`。
    - `context_budget_for_view(view) -> ContextBudget`。
  - `PreparedMainRequest`（frozen）：`request, request_id, projection_fingerprint, tool_result_part_ids`。
  - `_AgentLoopLimitReached(Exception)`（内部）。
- **核心流程**：见 1.3 的伪代码（已覆盖 `run_user_turn → _run_user_turn_sync_impl → _run_tool_loop_interactive → _complete_turn`）。
  补充关键子路径：
```
_prepare_main_provider_request()：
  repair interrupted tail → check_cancelled → append pending guidance →
  append background notifications → _provider_tool_definitions()
  view = rebuild_view()
  budget = build_context_budget(messages, tools, context_window, max_tokens)
  if context_manager: result = context_manager.compact_if_needed(
       ContextCompactRequest(view, runtime_state, budget, estimate_budget, trigger=AUTO,
                             current_turn))
    if success: view = rebuild_view()
  messages = _request_messages(view, runtime_instruction)
  request = ChatRequest(messages, definitions, tool_choice)
  fingerprint = stable_json_hash({"messages": [...], "tools": [...]}, length=24)

_complete_once_with_recovery()：
  loop:
    try: return _complete_once(...)
    except ProviderError as e:
      if e.retryable and retries < policy.max_retries: 退避重试
      if e.requires_compaction and not compaction_attempted:
         compact_for_prompt_too_long()；success 则 continue
      raise

_continue_tool_loop_from_response(response, complete_once, tool_rounds)：
  while response.tool_calls:
    if tool_rounds >= max_tool_rounds: return _tool_round_limit_response
    session.append_assistant_response(response)         # 先写 assistant tool_call
    execution = tool_executor.execute_interactive(response.tool_calls)
    if execution.pending_input: return (response, pending_input, tool_rounds)
    if execution.task_hash_changed: _compact_after_task_hash_changed()
    tool_rounds += 1
    response = _drop_unsupported_tool_calls(complete_once())
  return (response, None, tool_rounds)
```
- **与相邻模块的关系**：
  - 依赖：`AgentSession`、`ContextBuilder`、`ContextManagerLike`（Protocol）、`ChatProvider`、`ToolCallSettlement`、`ToolExecutor`、`TaskBoundaryClassifier`、`TaskPlanPolicy`、`ExecutionEvidence`、`StagnationGuard`、`AgentTurnTelemetry`、`BackgroundJobManager`、`SubagentRunner`。
  - 被依赖：`app/runtime.AgentChatRunner`（创建并驱动 AgentLoop）、`agent/subagent`（子代理内嵌 AgentLoop）。
- **设计原理**：
  - 把 AgentLoop 理解成「单轮事务」：先落库、再投影、再调用、再结算。所有事实先写 JSONL，运行期对象只是缓存。
  - **关键顺序不变量**：必须先 `append_assistant_response`（写 tool_call）再 `append_tool_result`（写 tool_result），provider 后续才看到合法配对。
  - **权限暂停**：`ASK` 时不写任何 tool_result，而是把 pending 存在 `session.pending_permission_execution`，让 UI 恢复。恢复时用 session 保存的原始 tool_call，不信任 UI 回传参数。
  - **`_provider_tool_definitions` 是运行时过滤层**：按 `runtime_capabilities`（think/web_search/ask_user/planning）、MCP 激活集、后台允许列表裁剪 schema，避免把模型无法真正使用的工具暴露出去。
  - **压缩触发分散在多处**：AUTO（每次请求前）、PROMPT_TOO_LONG（provider 报错）、TASK_HASH_CHANGED（task_boundary 确认切换）。loop 不判断 token 细节，只发「可能需要整理」信号。
  - **streaming 与 sync 双实现**：`_run_tool_loop_interactive` / `_run_tool_loop_interactive_async` 语义一致；文本 delta 可即时展示，工具调用保持原子（等 `message_completed`）。
  - **benchmark 门禁**：`_run_completion_gate_if_needed` 只在 benchmark 能力开启时注入 gate 指令。
- **隐藏的坑 / 边界**：
  - `_tool_round_limit_response` 只写纯文本，**避免把未执行的 tool_call 存进历史**。
  - `_drop_unsupported_tool_calls`：不支持工具的 provider 若仍返回 tool_calls，全部丢弃并写 diagnostics。
  - `_stream_once_attempt`：流式尝试失败时丢弃已收 delta，避免把局部输出当真实回答。
  - 后台通知 `_append_background_notifications` 生成的 `<task_notification>` 是独立 user 消息，**绝不复用原 tool_call_id**，保持一对一的 tool_result 配对。
- **重写标注**：`【保留】`（核心 spine，逐行理解后照搬语义）。

### 📌 `agent/session.py`（674 行）—— 重点精读
- **职责**：Agent 会话运行时容器，连接 context store、runtime state、system prompt 缓存与 session-scoped 工具。不调用模型、不执行压缩。
- **对外 API**：
  - `AgentSession`（slots dataclass）字段：`session_id, store, runtime_state, tool_registry, writer, agents_md, skill_catalog, base_rules, prompt_cache, prompt_builder, provider_capability_overrides, permission_manager, permission_policy, sandbox_access, known_message_ids, turn_counter, mode, benchmark_task, require_prewrite_review, pending_permission_execution`。
  - 类方法：`create(...)`、`from_project(...)`、`resume(...)`。
  - 实例方法：
    - `restore_pending_permission_execution() -> PendingPermissionExecution | None`。
    - `persist_pending_permission_kind(*, tool_call_id, review_only)`。
    - `pending_permission_input_request(pending=None) -> UserInputRequest | None`。
    - `append_session_created()`。
    - `build_system_prefix(*, provider_name, provider_model="", provider_capabilities=None) -> list`。
    - `set_benchmark_task(task)`。
    - `append_user_message(content, *, attachments=None) -> str`。
    - `append_assistant_response(response) -> str`。
    - `record_provider_projection_consumed(*, request_id, projection_fingerprint, part_ids, provider, model)`。
    - `execute_tool_call(tool_call)`、`preflight_tool_call_permission(tool_call)`、`execute_tool_call_after_permission_confirmation(tool_call)`。
    - `set_permission_mode(mode)`。
    - `append_tool_result(*, tool_call, result) -> str`（幂等，`_tool_result_message_ids` 去重）。
    - `append_interrupted_tool_results() -> list[ToolCall]`。
    - `append_background_notification(...)`。
    - `rebuild_view()`。
  - `PendingPermissionExecution`（dataclass）：`request_id, tool_call, permission_request, prewrite_review, review_only, skipped_tool_calls`。
  - `ToolPermissionPreflight`：`request, decision`。
  - `create_project_permission_manager(project_root, *, grants=None, mode=STANDARD)`。
- **核心流程**：
```
create()：
  runtime_state = SessionRuntimeState(session_id)
  writer = SessionEventWriter(store, session_id)
  registry = create_session_tool_registry(session_id, runtime_state, tools, known_message_ids,
              task_boundary_required_stable_count, permission_manager, archive_root=store.root,
              current_turn=lambda: writer.current_turn, store, writer, skill_catalog)
  session = cls(...)；_sync_sandbox_access_with_mode()；append_session_created()

resume()：
  runtime_state = replay_runtime_state(store, session_id)
  view = store.rebuild_session_view(session_id)
  known_message_ids = {message.id for message in view.messages}
  turn_counter = 用户消息数
  writer = SessionEventWriter(store, session_id, current_turn=turn_counter)
  registry = create_session_tool_registry(...)（同上）
  _tool_result_message_ids = 从 view 重建（tool_result part → message.id）

append_tool_result(tool_call, result)：
  with _tool_result_lock:
    if tool_call.id in _tool_result_message_ids: return 旧 message_id   # 幂等
    message_id = new_message_id()
    part = tool_result_to_part(...)   # metadata 存 tool_call_id/tool_name/ok/data/error
    writer.append_tool_result_part(part, message_id)
    _tool_result_message_ids[tool_call.id] = message_id
    if tool_call.name == task_boundary and result.ok:
       observation → writer.append_task_boundary_observation(observation)
```
- **与相邻模块的关系**：依赖 `context`（store/writer/runtime_state/runtime_replay/system_prompt/task_boundary/identity）、`permissions`、`providers.types`、`runtime.user_input`、`tools`（session_registry/review/permission_registry/types）、`skills`、`input.attachments`、`utils.sandbox_access`。被 `agent/loop`、`agent/subagent`、`session/bootstrap`、`app/runtime` 依赖。
- **设计原理**：
  - AgentSession 是「运行期容器」，可 resume 事实通过 writer 追加 JSONL。
  - `known_message_ids` 用于 task_boundary 工具校验 basis_message_id 合法性，resume 时务必回填。
  - `_tool_result_message_ids` 让 `append_tool_result` 幂等，同一 tool_call_id 只落一条 tool_result——这是「resume 后 settlement 幂等」的根基。
  - `build_system_prefix` 不写普通消息：system prompt 是每次请求按 AGENTS.md/provider 能力/权限策略动态生成的高优先级前缀；工具 schema 走 provider 原生 tools 字段。
  - `restore_pending_permission_execution` 只在历史尾部恰好有一个未闭合 assistant tool_call 批次时重建，且只恢复 pending 不自动执行（避免 resume 隐式副作用）。
- **重写标注**：`【保留】`。

### `agent/user_input.py`（46 行）
- **职责**：turn 结果类型。
- **对外 API**：`AgentTurnStatus(StrEnum)`（COMPLETED / WAITING_FOR_USER_INPUT）；`AgentTurnResult`（`status, response: ChatResponse|None, pending_input: UserInputRequest|None`，附 `content/finish_reason/tool_calls/diagnostics` 便捷属性）。
- **重写标注**：`【保留】`。

### `agent/ports.py`（13 行）
- **职责**：稳定协议端口。`ContextManagerLike` Protocol（`compact_if_needed`）。
- **重写标注**：`【保留】`。

### `agent/loop_limits.py`（58 行）
- **职责**：turn 预算与停止原因。
- **对外 API**：`AgentLoopStopReason(StrEnum)`（TOOL_ROUND_LIMIT / PROVIDER_CALL_LIMIT / TURN_TIMEOUT）；`AgentLoopLimits`（`max_tool_rounds=200, max_provider_calls=400, max_turn_seconds=3600`；`default()/swe_lite()/summary()`；`with_max_tool_rounds(value, *, provider_call_reserve=0)`）。
- **重写标注**：`【保留】`。

### `agent/provider_retry.py`（24 行）
- **职责**：provider 瞬态失败退避策略。
- **对外 API**：`ProviderRetryPolicy(max_retries=2, initial_delay=1.0, multiplier=2.0, max_delay=8.0)`；`delay_for_retry(n)`。`DEFAULT_PROVIDER_RETRY_POLICY`。
- **重写标注**：`【保留】`。

### `agent/runtime_capabilities.py`（76 行）
- **职责**：Agent 运行能力配置与 benchmark 工具路由。
- **对外 API**：
  - `AgentRuntimeCapabilities`（frozen）：`allow_user_input, enable_completion_gate, enable_stagnation_guard, enable_delegate_tool, expose_planning_tools, expose_think_tool, expose_web_search_tool, enable_process_tools, background_tool_names`。
  - `interactive()` / `benchmark(task)` 类方法。
  - `benchmark_task_is_complex(task) -> bool`（≥1200 字符 / ≥3 列表项 / ≥2 复杂关键词）。
  - `PLANNING_TOOL_NAMES = {task_create, task_update, task_revise, task_list}`。
  - `BENCHMARK_BACKGROUND_TOOL_NAMES = {diagnostics, shell, python_exec, fetch, delegate}`。
- **设计原理**：把散落的 benchmark 分支收敛成单一装配点；loop 只查 capability 字段。
- **重写标注**：`【简化】`（去掉 benchmark 分支，保留 interactive 即可）。

### 📌 `agent/tool_execution.py`（619 行）—— 重点精读
- **职责**：工具执行的并行批策略、交互式顺序、权限 pending 存储、tool-event 发射。
- **对外 API**：
  - `ToolExecutionEvent`：`kind, tool_call, result, permission_request, prewrite_review`。kind ∈ {prewrite_review, started, finished, permission_requested, denied, skipped, interrupted, background_started}。
  - `ToolExecutionState`：`task_hash_changed, pending_input`。
  - `ToolExecutor` 类。关键方法：`execute_interactive(tool_calls) -> ToolExecutionState`、`execute_interactive_async(...)`、`execute_single`、`execute_parallel_readonly_batch`、`execute_after_permission_with_cancellation_context`、`store_pending_permission_request`、`permission_input_request_from_pending`。
  - 模块常量：`PARALLEL_READONLY_TOOL_NAMES`、`BYPASS_PARALLEL_TOOL_NAMES`。
- **核心流程**：
```
execute_interactive(tool_calls)：
  tool_calls, background_request = _normalize_background_controls(tool_calls)  # 剥离控制面字段
  index = 0
  while index < len(tool_calls):
    validation_error = validate(tool_call)  # MCP 激活 / 运行时可见性 / stagnation
    if validation_error: record + emit denied; index++; continue
    if tool_call.name in HIDDEN_TOOL_STATUS_NAMES: denied; index++; continue
    permission = _prepare_permission(tool_call, remaining)   # 权限预检
    if permission.result:  denied + record; index++; continue
    if permission.pending_input: emit permission_requested; return pending_input   # 暂停
    if tool_call.id in background_request: dispatch_background(...); record; index++; continue
    if can_execute_in_parallel(tool_call): 并行只读批执行; index = batch_end; continue
    result = execute_single(tool_call)
    pending_input = _record_result(tool_call, result, skipped_tool_calls=剩余)
    if pending_input: return pending_input
    index++
```
- **与相邻模块的关系**：依赖 `AgentSession`、`ToolCallSettlement`、`BackgroundJobManager`、`TaskPlanService`、`WorktreeManager`、`build_prewrite_review`、`permission_results` 等。被 `agent/loop` 依赖。
- **设计原理**：
  - **先权限、后执行、再结算**。权限在副作用前预检；ASK 时暂停并保存 pending；只有 ALLOW/无预检的工具才执行。
  - **后台控制面字段在 executor 入口统一剥离**，executor 永远看不到 `run_in_background` 等字段；后台请求按 tool_call_id 记录，权限放行后才转入后台，保证「绝不后台执行需要确认的工具」。
  - **并行只读批**：只有当前模式允许的只读工具且权限已 ALLOW 才能同批并行。
  - `_record_result` 在落库前调用 observer（`_observe_tool_result`），observer 可以给结果附加一次性 agent guidance，但不能绕过权限或再执行工具。
  - `_dispatch_background` 返回占位结果闭合原 tool_call_id；真正的完成结果由 `BackgroundJobManager.collect_completed` 作为 notification 注入。
- **重写标注**：`【保留】`。

### 📌 `agent/tool_settlement.py`（56 行）—— 重点精读
- **职责**：保持 provider 历史中 tool_call / tool_result 的闭合关系。
- **对外 API**：`SettledToolCall(tool_call, result)`；`ToolCallSettlement(session)`：`append_skipped(tool_calls)`、`append_interrupted_tail()`、`repair_before_provider_request()`。
- **核心流程**：
```
append_skipped(tool_calls)：为「等待用户输入而跳过」的同批后续工具写 error 结果
append_interrupted_tail()：session.append_interrupted_tool_results() → 把历史尾部未闭合
  tool_call 写成 interrupted 结果（"结果未知，操作可能尚未执行..."）
repair_before_provider_request()：若没有 pending_permission_execution，先补 interrupted tail，
  保证 provider 请求前消息序列合法
```
- **设计原理**：这是「tool_call/tool_result 配对完整性」的兜底层。任何中断/跳过/暂停都不能让历史悬空 tool_call。
- **重写标注**：`【保留】`。

### `agent/tool_flow.py`（43 行）
- **职责**：tool calling 协议写入与校验 helper。
- **对外 API**：`assistant_response_to_parts(*, message_id, response)`、`tool_result_to_part(*, message_id, tool_call, result)`。
- **设计原理**：集中转换，避免 tool_call_id/arguments 字段漂移。
- **重写标注**：`【保留】`。

### 📌 `agent/execution_evidence.py`（506 行）—— 重点精读
- **职责**：benchmark 执行证据与最终答复门禁。记录当前用户回合已发生的修改/验证/后台任务证据。
- **对外 API**：
  - `ExecutionEvidence`（slots）：字段 `sequence, last_mutation_sequence, last_mutation_tool, last_validation_sequence, last_validation_tool, last_validation_ok, validation_attempts, failed_tool_calls, background_job_ids, explicit_validation_targets, explicit_validation_expectations, last_validation_command, last_validation_assertive`。
    - `for_task(task)`（从题面提取显式 HTTP 目标与预期）、`reset()`、`observe(tool_call, result)`、`completion_decision(*, background_jobs) -> CompletionGateDecision`、`render_acceptance_contract()`。
  - `CompletionGateDecision(reasons)`：`required`、`render_instruction()`。
  - `ExplicitValidationExpectation`：`target, expected_statuses, expected_outputs`；`missing_from_command(command)`、`render()`。
  - 模块函数：`is_validation_call(tool_call)`、`is_mutation_result(tool_call, result)`、`has_resetting_success(...)`、`explicit_validation_targets(task)`、`explicit_validation_expectations(task)`、`validation_is_assertive(tool_call)`。
- **核心流程**：
```
observe(tool_call, result)：
  忽略控制结果（requires_user_input/skipped/interrupted/stagnation_blocked/permission_*）
  sequence += 1
  validation = is_validation_call；mutation = result.ok and is_mutation_result
  if mutation: last_mutation_sequence = sequence
  if validation: validation_attempts++；记录命令文本与是否 assertive；last_validation_ok =
      result.ok and (assertive or 输出不含失败 HTTP 状态)
  if not result.ok: failed_tool_calls++

completion_decision(background_jobs)：
  收集 reasons：
    - 相关后台任务仍在 running / failed
    - last_validation_ok is False（最近一次验证失败）
    - 最近一次修改后没有验证（last_validation_sequence < last_mutation_sequence）
    - 最近验证没有覆盖题面显式目标 / 预期输出
    - 最近验证是信息性的（shell/python_exec 且非 assertive）
  return CompletionGateDecision(reasons)

is_mutation_result：MUTATION_TOOL_NAMES{write,edit,apply_patch,delete} 或
  PROCESS_MUTATION_TOOL_NAMES{process_start,process_stop} 或 git_diff 有真实 diff 或
  shell/python_exec 命令匹配 _MUTATION_COMMAND_RE
```
- **与相邻模块的关系**：被 `agent/loop`、`agent/stagnation`、`agent/telemetry` 依赖。
- **设计原理**：只记录已发生事实，不判断题目是否真过 verifier；职责是阻止「修改后完全没验证 / 最后一次验证失败 / 后台任务未结束」这类过早收尾。大量正则用于从 shell 命令里识别验证/修改意图。
- **隐藏的坑**：`is_mutation_result` 依赖命令文本启发式（`rm|pip install|>>...`），易误判；这是 benchmark 专用，普通交互模式不启用。
- **重写标注**：`【必须改】`（benchmark 门禁是 Terminal-Bench 特有，重写若不做 benchmark 可整体移除；保留 `is_validation_call/is_mutation_result` 思路可简化复用）。

### 📌 `agent/stagnation.py`（179 行）—— 重点精读
- **职责**：benchmark 工具停滞检测。识别「相同参数产生相同失败」并在第四次执行前阻断。
- **对外 API**：`StagnationGuard`：`reset()`、`validate(tool_call) -> ToolResult|None`、`observe(tool_call, result) -> str|None`；`append_guidance(result, guidance)`。
- **核心流程**：
```
observe(tool_call, result)：
  忽略控制结果；若 has_resetting_success → reset() 返回 None
  if result.ok: return None
  fingerprint = sha256(call_key + ok + error + exit_code + output_tail)
  count = failure_counts[fingerprint] + 1
  if count >= 3: blocked_call_keys.add(_call_key(tool_call))   # 第 4 次被 validate 阻断
  count==2 → guidance "same failure twice..."
  count==3 → guidance "stagnation guard armed..."
validate(tool_call)：若 call_key 在 blocked_call_keys → 返回 blocked 错误结果
append_guidance(result, guidance)：把一次性策略提示追加到 ToolResult.content 和 data.agent_guidance
```
- **设计原理**：停滞状态只存在于当前用户回合，不写入长期会话事实；新任务边界不继承上一题失败计数。
- **重写标注**：`【简化】`（benchmark 特有，可后置；思路（相同失败计数阻断）值得保留）。

### 📌 `agent/telemetry.py`（158 行）—— 重点精读
- **职责**：Agent 用户回合遥测（结构化计数）。
- **对外 API**：`AgentTurnTelemetry`：`begin(...)`、`observe_provider_call()`、`observe_provider_retry(kind)`、`observe_tool_result(tool_call, result, *, elapsed_seconds)`、`observe_completion_gate(reason_count)`、`snapshot(*, status, stop_reason, elapsed_seconds, provider_failure_category, finalize) -> dict|None`。
- **核心流程**：`snapshot` 生成 `{schema_version, turn_number, snapshot_index, status, stop_reason, elapsed_seconds, provider_calls, provider_retries, provider_retry_categories, tool_calls, tool_failures, tool_call_counts, repeated_tool_calls, max_identical_tool_calls, first_mutation_sequence/elapsed, validation_count, latest_validation_ok/tool, completion_gate_used/reason_count}`。
- **设计原理**：只保存控制循环结构化计数，**不保存提示词、工具参数、工具输出、密钥**；事件持久化但不会被投影成 provider 消息。
- **重写标注**：`【保留】`（可观测性核心）。

### `agent/task_boundary_classifier.py`（133 行）—— 重点精读
- **职责**：隐藏 LLM 任务边界分类。这是「先判断新任务，再进主回复」的隐藏调用。
- **对外 API**：`TaskBoundaryClassifier(session, provider, request_options, context_builder, compact_if_needed, check_cancelled, reserve_provider_call, check_turn_timeout, tag_task_boundary_messages)`；`classify(basis_message_id)`、`classify_async(...)`、`build_request(attempt)`、`record(decision, basis_message_id)`；`parse_task_boundary_classification(content, *, basis_message_id)`。
- **核心流程**：
```
classify(basis_message_id)：
  for attempt in range(3):
    request = build_request(attempt)  # system=CLASSIFICATION_PROMPT + provider messages, tools=[]
    response = provider.complete(request)
    decision = parse(content)   # 必须是 {"decision":"same|new|uncertain","basis_message_id":...}
    if decision: record(); return
  record("uncertain")   # 3 次失败降级 uncertain
record(decision, basis_message_id)：
  执行 task_boundary 工具（走正常工具注册表）→ observation → writer.append_task_boundary_observation
  若 should_trigger_compaction → _compact_if_needed(TASK_HASH_CHANGED)
```
- **设计原理**：分类调用不向 UI 转发任何事件；分类 prompt 强制「只做分类，不回答问题」；basis_message_id 必须精确等于当前用户消息 id。
- **重写标注**：`【简化】`（隐藏分类调用思路通用，但 prompt 与降级策略可自定；非必须）。

### `agent/task_plan_policy.py`（65 行）
- **职责**：读取持久化 TaskPlan，返回可选的 loop 指令。
- **对外 API**：`TaskPlanPolicy(session)`：`final_reconciliation_instruction() -> str|None`；`render_current_task_plan_snapshot(plan) -> str`。
- **核心流程**：plan 存在且有未完成任务 → 返回「先 reconcile 未完成任务」的 system 指令；否则 None。
- **重写标注**：`【简化】`（TaskPlan 是可选能力）。

### `agent/prompt_inputs.py`（133 行）
- **职责**：system prompt 输入装配。
- **对外 API**：`DEFAULT_PERMISSION_POLICY`（path_access=project_root_only, read=allow, write/delete/shell/network/mcp_tools=confirm, env_secrets=redact）；`read_agents_md(project_root)`；`provider_capabilities_for(provider_name, *, provider_model="")`；`provider_capabilities_from_instance(...)`；`build_system_prompt_inputs(...)`。
- **设计原理**：静态能力表（anthropic 用 separate_field，其余 openai_compatible）是刻意的——真实 provider 还没有 capability discovery 协议。
- **重写标注**：`【保留】`。

### 📌 `agent/background.py`（448 行）—— 重点精读
- **职责**：通用异步工具运行时（Phase 1）。把同步工具执行放后台线程，完成后产出一条可注入的 notification。
- **对外 API**：
  - 控制面字段常量：`RUN_IN_BACKGROUND_ARG, BACKGROUND_LABEL_ARG, BACKGROUND_TASK_ID_ARG, BACKGROUND_CONTROL_ARGS`。
  - `DEFAULT_BACKGROUND_TOOL_NAMES`。
  - 状态字面量：`STATUS_RUNNING/COMPLETED/FAILED/CANCELLED`。
  - `with_background_controls(definition) -> ToolDefinition`（给 schema 附加后台控制字段）。
  - `strip_background_controls(arguments) -> (clean, run_in_background, label, task_id)`。
  - `has_background_control_fields(arguments)`。
  - `BackgroundNotification`：`job_id, tool_name, status, summary, ok, session_id, label, task_id, observed_revision, task_plan_completion, kind`。
  - `BackgroundJob`：`id, tool_name, session_id, label, task_id, observed_revision, status, result, error, cancel_requested, created_at, token, on_completed, task_plan_completion`；`snapshot()`。
  - `BackgroundJobManager`：`start(func, *, session_id, tool_name, label, task_id, observed_revision, on_completed)`、`collect_completed(session_id=None)`、`get/list/cancel/wait/shutdown`。
  - `BackgroundCapacityError`；`make_background_placeholder_result(job)`；`render_task_notification(notification)`。
- **核心流程**：
```
start(func)：
  active = 运行中任务数；>= max_jobs → raise BackgroundCapacityError
  job_id = f"bg_{counter:04d}"；提交 _executor.submit(_run, job, func)
_run(job, func)：with cancellation_context(job.token): result = func()；_finish(job, ...)
_finish(job, result, error)：cancel_requested → CANCELLED；error → FAILED；result not ok → FAILED；
  否则 COMPLETED；入 _completed 队列
collect_completed(session_id=None)：
  lock 下取出该 session 的 completed jobs
  每个 job：_finalize_task_plan_completion（若 status==COMPLETED 且 on_completed 存在，串行执行，
    避免与正常 session 事件写入竞争）→ 构造 notification
cancel(job_id)：future.cancel() 成功 → CANCELLED；否则 cancel_requested=True + token.cancel()
```
- **与相邻模块的关系**：依赖 `providers/types`、`runtime/cancellation`、`tools/types`。被 `agent/loop`、`agent/tool_execution`、`tools/background`、`app/factory` 依赖。
- **设计原理**：刻意不认识 AgentLoop/ToolExecutor/session；后台执行不等同于让原始 tool_call 悬空——**原始 tool_call_id 立刻得到占位 tool_result**，真正结果稍后作为独立 `<task_notification>` 用户消息注入。
- **重写标注**：`【保留】`（若重写需要后台能力；否则 `【暂缓】`）。

### 📌 `agent/subagent.py`（557 行）—— 重点精读
- **职责**：delegate 工具的子代理 runner。子会话全新 + metadata 标记 + 工具按角色裁剪 + 不递归。
- **对外 API**：
  - `SubagentRole = Literal["researcher","reviewer","tester","coder"]`。
  - `SUBAGENT_PROFILES`：role → `SubagentProfile(role, description, allowed_tool_names, allow_background, requires_worktree)`。
  - `SUBAGENT_ROLE_LIMITS`：role → `AgentLoopLimits`。
  - `SubagentRequest`：`role, task, parent_session_id, parent_task_hash, parent_summary, path_hints, run_in_background, isolate_worktree`。
  - `SubagentResult`：`ok, role, child_session_id, summary, evidence, files_changed, error, worktree_path, worktree_branch, diff_summary`。
  - `SubagentRunner`：`profile(role)`、`tools_for_role(role)`、`limits_for_role(role)`、`run(request)`、`create_child_session(...)`。
- **核心流程**：
```
run(request)：
  profile 不存在 → error；run_in_background 且不允许 → error
  _needs_worktree(request, profile)（isolate_worktree 或 coder+background）→ _run_isolated
  否则 _run_inline
_run_inline：create_child_session（AgentSession.create + append metadata parent_*）
  AgentLoop(session=child, provider, tools_for_role, limits, background_manager=None,
            enable_delegate_tool=False)
  asyncio.run(loop.run_user_turn(prompt)) → 只返回紧凑 summary
_run_isolated：
  WorktreeManager(project_root).create(session_id) → worktree
  child = _create_isolated_child_session（permission_manager 根指向 worktree，SandboxAccess=PROJECT，
    require_prewrite_review=False）
  AgentLoop(...) 运行；完成 → manager.diff(worktree) 返回 diff summary（不自动 merge）
_child_permission_manager(root)：AGGRESSIVE 模式 + 对 worktree 根的 write/delete grant + 全新 grant store
```
- **设计原理**：Phase 4 worktree 隔离保证「后台 coder 绝不触碰父工作区」；子代理无 delegate 工具防递归；隔离 coder 的写前预览禁用（无交互用户），由父代理审查 worktree diff。
- **重写标注**：`【简化】`（子代理是可选能力；worktree 隔离若不需要可去掉）。

### `agent/worktree.py`（222 行）
- **职责**：Phase 4 git worktree 隔离。
- **对外 API**：`Worktree(name, path, branch, base_ref)`；`WorktreeDiff(stat, files_changed, has_changes)`；`WorktreeManager(project_root)`：`available(base_ref="HEAD")`、`create(name, base_ref)`、`diff(worktree)`、`is_dirty(worktree)`、`remove(worktree, *, force=False)`；`is_git_repo(path)`。
- **核心流程**：worktree 存于 `<git-common-dir>/fc-worktrees/<name>`（git 目录内，不污染父 status/sandbox）；创建 `git worktree add -b fc/subagent/<name>`；diff 用 `git add -A -N` + `--stat` + `--name-status`。
- **重写标注**：`【暂缓】`。

### `agent/processes.py`（195 行）
- **职责**：结构化长期进程管理。
- **对外 API**：`ManagedProcess`；`ProcessStartOutcome`；`ProcessManager(log_root, ...)`：`start(command, *, cwd, env, label, ready_pattern, ready_timeout_seconds)`、`get/list/logs/stop/shutdown`。
- **核心流程**：独立进程组启动；stdout/stderr 写日志文件；`ready_pattern` 轮询日志判断就绪；CLI 退出后子进程仍存活（父进程关闭文件句柄），TUI 卸载时显式回收。
- **重写标注**：`【简化】`（Terminal-Bench 需要，普通 agent 可后置）。

---

## 6. Provider 层（providers/ 全部）

### 📌 `providers/base.py`（60 行）—— 重点精读
- **职责**：provider 抽象接口。
- **对外 API**：`ChatProvider(ABC)`：`name`、`model`（property）；`complete(request) -> ChatResponse`（抽象）；`acomplete(request)`（默认 `asyncio.to_thread(complete)`）；`astream(request)`（默认抛 UNSUPPORTED）。
- **设计原理**：agent 主循环只依赖这个接口，不直接依赖 OpenAI/Anthropic SDK。默认 `astream` 给出稳定内部错误语义。
- **重写标注**：`【保留】`。

### 📌 `providers/types.py`（197 行）—— 重点精读
- **职责**：provider 层共享数据结构。
- **对外 API**（frozen/slots dataclass 为主）：
  - `MessageRole/FinishReason/TokenParam/ToolChoiceMode/StreamEventKind`（Literal 类型）。
  - `ProviderCapabilities`：`supports_tools, supports_forced_tool_choice, supports_streaming, supports_parallel_tool_calls, supports_json_mode, supports_vision, supports_reasoning, token_param`。
  - `TokenUsage`：`input_tokens, output_tokens, total_tokens`。
  - `ProviderDiagnostics`：`reasoning, raw_finish_reason, warnings`。
  - `ContentPart`：`type(text|image), text, media_type, data_base64, filename`。
  - `ChatMessage`：`role, content, content_parts, name, tool_call_id, tool_calls`。
  - `ToolDefinition`：`name, description, parameters`（JSON Schema 风格）。
  - `ToolCall`：`id, name, arguments`（dict 或 str）。
  - `ToolChoiceFunction`：`name`；`ToolChoice = ToolChoiceMode | ToolChoiceFunction`。
  - `MainRequestOptions`：`temperature, max_tokens, extra_body`；`as_chat_request_kwargs()`。
  - `ChatRequest`：`messages, tools, tool_choice, temperature, max_tokens, extra_body`。
  - `ChatResponse`：`provider, model, content, tool_calls, finish_reason, usage, diagnostics, raw`。
  - `ChatStreamEvent`：`kind, text, tool_call, tool_call_index, tool_call_id, tool_name, arguments_delta, response, diagnostics`。
- **设计原理**：所有厂商方言都收敛到这组内部类型；`ToolCall.arguments` 允许 str（解析失败时保留原串，不执行）。
- **重写标注**：`【保留】`。

### 📌 `providers/errors.py`（112 行）
- **职责**：provider 错误分类。
- **对外 API**：`ProviderErrorKind(StrEnum)`（PROMPT_TOO_LONG/TIMEOUT/RATE_LIMIT/AUTH_ERROR/CONFIG_ERROR/UNSUPPORTED/SERVER_ERROR/API_ERROR/USER_ABORT/NETWORK_ERROR/UNKNOWN）；`ProviderError(kind, message)` 带 `retryable`、`requires_compaction` property；`classify_provider_exception(exc)`、`classify_provider_error(message, *, status_code)`。
- **设计原理**：agent loop 只依赖分类决定重试/压缩/提示，不解析厂商错误字符串。
- **重写标注**：`【保留】`。

### 📌 `providers/streaming.py`（130 行）—— 重点精读
- **职责**：把同步 provider 流适配成 async 消费者的共享 helper。
- **对外 API**：`read_field`、`StreamFailure`、`StreamToolCallAccumulator`、`STREAM_ENDED`、`token_usage`、`merge_usage`、`complete_stream_tool_calls(accumulators, diagnostics, *, require_identity)`、`close_stream`、`start_sync_stream_worker(stream, *, thread_name)`。
- **核心流程**：
```
start_sync_stream_worker：线程里 for item in stream: queue.put(item)；异常→StreamFailure；结束→STREAM_ENDED
complete_stream_tool_calls：按 index 排序累积器；require_identity 时 id/name 必须齐全；
  arguments_text 必须是合法 JSON object；否则丢弃整组并写 warning
```
- **设计原理**：OpenAI/Anthropic 的流迭代器是同步对象，用后台线程读 + Queue 桥接 async loop，避免阻塞 Textual。
- **重写标注**：`【保留】`。

### `providers/tool_adapters.py`（30 行）
- **职责**：内部 ToolDefinition → OpenAI/Anthropic 工具格式。
- **对外 API**：`to_openai_tool(tool)`、`to_anthropic_tool(tool)`。
- **重写标注**：`【保留】`。

### `providers/presets.py`（111 行）
- **职责**：常见厂商 provider 预设（openai/deepseek/qwen/moonshot/zhipu/openrouter/ollama/anthropic）。
- **对外 API**：`ProviderPreset`；`PROVIDER_PRESETS` dict。
- **重写标注**：`【保留】`（可删掉不需要的厂商）。

### `providers/factory.py`（114 行）
- **职责**：provider 构造入口。
- **对外 API**：`create_provider_for_model(config, profile) -> ChatProvider`；`ProviderConfigError`。
- **核心流程**：`profile.provider.type` 在 `{"openai-compatible","custom"}` → `_create_catalog_openai_compatible`；在 `PROVIDER_PRESETS` → `_create_catalog_preset`；否则报错。api_key 缺省用 `FIRSTCODER_API_KEY`，ollama 特判 `"ollama"`。
- **重写标注**：`【保留】`。

### `providers/openai_compatible.py`（471 行）—— 重点精读
- **职责**：OpenAI Chat Completions 协议 provider（覆盖 DeepSeek/Qwen/OpenRouter/Ollama 等）。
- **对外 API**：`OpenAICompatibleProvider`（`name, model, api_key, base_url, capabilities, extra_headers, extra_body, client`）；`complete(request)`、`astream(request)`。
- **核心流程**：
```
complete：
  params = _build_completion_params(request)
    # messages 转 OpenAI 格式；tools 转 function tool；tool_choice 转 wire；temperature/max_tokens
    # extra_body 透传厂商私有参数（不覆盖核心字段）
  response = client.chat.completions.create(**params)
  choice = response.choices[0]；finish_reason 归一化
  tool_calls = _parse_tool_calls(...)；若 finish_reason=="length" 且存在 tool_calls → 丢弃整组
  usage = _parse_usage(...)  # prompt_tokens/completion_tokens/total_tokens
astream：
  stream = client.chat.completions.create(stream=True)
  start_sync_stream_worker 桥接；逐 chunk 解析：
    text → content_parts；reasoning_content/reasoning → reasoning_parts
    tool_calls delta 按 index 累积到 tool_accumulators
  stream 结束后：finish_reason != "tool_calls" → 丢弃累积 tool_calls；
    否则 complete_stream_tool_calls(require_identity=True)
  产出 tool_call_completed 事件 → message_completed(response)
```
- **设计原理**：`arguments` 解析失败不「修复」也不执行其中一部分（副作用不能靠猜）；`parallel_tool_calls` 只在 preset 声明支持时发送。
- **重写标注**：`【保留】`。

### `providers/anthropic_provider.py`（540 行）—— 重点精读
- **职责**：Anthropic Messages API provider。
- **对外 API**：`AnthropicProvider`（构造参数同 openai_compatible，`client` 可注入）。
- **核心流程**：
```
complete：
  params = _build_message_params(request)
    # system 抽到独立字段；messages 转 Anthropic 格式（tool_result 并入前一条 user 的 content
    #   列表；tool_use 在 assistant content 里）
    # max_tokens 必填（默认 4096）；tool_choice 转 {"type": "auto|none|any|tool","name":...}
  content_blocks 解析：text → content；tool_use → ToolCall；thinking → diagnostics.reasoning
  stop_reason 归一化：end_turn/stop_sequence→stop；tool_use→tool_calls；max_tokens→length
astream：类似 OpenAI，但 content_block_start/delta 处理 input_json_delta（partial_json）
```
- **设计原理**：与 OpenAI-compatible 主线共享同一套 `ChatRequest/ChatResponse/ChatStreamEvent` 契约，agent/TUI 无分支切换。
- **重写标注**：`【保留】`（若重写只接 OpenAI-compatible 可延后）。

### `providers/__init__.py`（41 行）
- **职责**：导出 provider 公共类型与工厂。
- **重写标注**：`【保留】`。

---

## 7. 权限层（permissions/ 全部）

### `permissions/types.py`（107 行）
- **职责**：权限系统基础类型。
- **对外 API**：
  - `PermissionAction(StrEnum)`：READ_PATH/WRITE_PATH/DELETE_PATH/EXECUTE_SHELL/NETWORK_REQUEST/GIT_OPERATION/READ_ENV/MCP_TOOL。
  - `PermissionMode`：STANDARD/AGGRESSIVE/BYPASS。
  - `PermissionDecisionKind`：ALLOW/DENY/ASK。
  - `PermissionPersistence`：ONCE/ALWAYS。
  - `PermissionScopeType`：EXACT_PATH/PATH_TREE/COMMAND_PREFIX/HOST/ENV_KEY/MCP_TOOL。
  - `PermissionConfirmationChoice`：DENY/REJECT_WITH_FEEDBACK/ALLOW_ONCE/ALLOW_ALWAYS_SAME_SCOPE。
  - `PermissionRequest`：`id, action, target, reason, cwd, metadata`。
  - `PermissionGrant`：`id, effect(allow|deny), action, scope_type, scope_value, created_at, reason`。
  - `PermissionDecision`：`kind, persistence, reason, feedback, grant`。
- **设计原理**：这些类型描述程序侧安全边界，不进入模型可见 tool schema。
- **重写标注**：`【保留】`。

### 📌 `permissions/manager.py`（297 行）—— 重点精读
- **职责**：权限统一决策入口。
- **对外 API**：`PermissionManager(policy, grants=None, mode=STANDARD)`：
  - `preflight(request) -> PermissionDecision`（grant 优先，其次 policy）。
  - `build_confirmation(request) -> UserInputRequest`（ASK → UI 可展示确认）。
  - `build_prewrite_review_confirmation(request)`（一次性操作审查门，不改 grant）。
  - `resolve_confirmation(request, choice) -> PermissionDecision`。
  - `normalize_request(request)`（相对 cwd 解析到项目根）。
- **核心流程**：
```
preflight：normalize → grants.matching_decision 命中即返回 → policy.decide(request, mode)
resolve_confirmation：
  choice 归一化：deny / reject_with_feedback / allow_once / allow_always_same_scope
  allow_once：_confirmation_guard（重新 preflight，若已不是 ASK 则返回新决策，防止把硬拒绝
    送进确认后创建 allow-always grant）；否则 ALLOW(ONCE)
  allow_always：构造 PermissionGrant（scope 按 action 类型：EXACT_PATH/COMMAND_PREFIX/HOST/ENV_KEY/MCP_TOOL）
    → grants.add → ALLOW(ALWAYS)
default_scope_for_request(request, project_root)：为 allow always 生成保守 scope
```
- **与相邻模块的关系**：依赖 `runtime/user_input`、`permissions/grants`、`permissions/policy`、`permissions/types`。被 `agent/session`、`tools/permission_registry`、`session/bootstrap` 依赖。
- **设计原理**：组合长期授权（grants）与默认策略（policy）。`normalize_request` 让相对路径与默认策略同一基准。
- **重写标注**：`【保留】`。

### 📌 `permissions/policy.py`（204 行）—— 重点精读
- **职责**：FirstCoder 默认权限策略（无显式 grant 时的安全底线）。
- **对外 API**：`DefaultPermissionPolicy(project_root)`：`decide(request, *, mode) -> PermissionDecision`。
- **核心流程**：
```
decide：
  BYPASS → 全 ALLOW
  READ_PATH：项目内且非敏感 → ALLOW；否则 ASK
  WRITE_PATH：项目外 → ASK；敏感路径(.env/.git/.pem/.key) → ASK；
    allow_auto=False → ASK；AGGRESSIVE + 项目内普通 → ALLOW；否则 ASK
  DELETE_PATH：项目外 → DENY（硬拒绝）；否则 ASK
  READ_ENV：敏感 key → DENY；否则 ASK
  GIT_OPERATION：含 shell 控制符 → ASK；只读 git(status/diff/log) 且在项目内 → ALLOW；否则 ASK
  EXECUTE_SHELL：含控制符 → ASK；AGGRESSIVE + 项目内 + 白名单命令 → ALLOW；
    危险命令(rm/sudo/curl/wget/pip...) → ASK
  NETWORK_REQUEST：私网/本机 → ASK；否则 ASK
  MCP_TOOL → ASK
```
- **设计原理**：激进模式可减少普通项目内写入确认，但不能绕过敏感环境变量、项目根外删除、敏感文件覆盖等硬边界。`_SHELL_CONTROL_PATTERN`（`&& || $( ; & | < > \` 换行`）是一票 ASK。
- **重写标注**：`【保留】`。

### `permissions/grants.py`（183 行）
- **职责**：内存/文件权限授权匹配。
- **对外 API**：`PermissionGrantStore`（`add/list/matching_decision`）；`FilePermissionGrantStore(path)`（`add` 后同步 `save()` 到 JSON）。
- **核心流程**：`matching_decision`：deny grant 永远优先于 allow；按 scope_type 匹配（EXACT_PATH/PATH_TREE/COMMAND_PREFIX/HOST/ENV_KEY/MCP_TOOL）。shell 命令含控制符时不匹配 COMMAND_PREFIX grant。
- **设计原理**：deny 优先避免后续 allow 规则意外放开更小范围的明确拒绝；持久化用原子写（tmp + replace）。
- **重写标注**：`【保留】`。

### `permissions/__init__.py`（35 行）
- **职责**：导出权限公共入口。
- **重写标注**：`【保留】`。

---

## 8. 规划层（planning/ 全部）

### `planning/models.py`（140 行）
- **职责**：任务规划领域模型与稳定 JSON 序列化。
- **对外 API**：`TaskStatus = Literal["pending","in_progress","completed","cancelled"]`；`TaskPlanMode = Literal["linear","dag"]`；`TaskPlanError`；`Task`（`id, content, status, depends_on, owner, order`）；`TaskPlan`（`mode, revision, tasks`）；均带 `from_dict/to_dict`（严格校验，未知字段/重复 id/非法状态抛错）。
- **重写标注**：`【保留】`。

### `planning/projection.py`（65 行）
- **职责**：纯派生视图。
- **对外 API**：`ordered_tasks(plan)`（按 order 排序）；`effective_dependencies(plan)`（dag 用显式依赖，linear 用前序隐式依赖）；`ready_task_ids(plan)`；`blocked_task_ids(plan)`；`topological_levels(plan)`（检测环）；`project_plan(plan)`（汇总 dict）。
- **重写标注**：`【保留】`。

### `planning/reducer.py`（361 行）
- **职责**：纯、原子的增量 reducer。
- **对外 API**：`create_tasks/update_tasks/revise_tasks`（均返回 `ReductionResult(plan, changes, changed)`）；`TaskPatch`、`TaskRevision`；`TaskPlanCommandError`、`TaskPlanRevisionConflict`。
- **核心流程**：
```
create_tasks：校验 expected_revision == 当前 revision；新建或追加；start_new_plan 要求所有旧任务终态
update_tasks：按 id patch status/owner/depends_on；产生 changes
revise_tasks：按 id 改 content
每个变更后 revision+1 并 _validate_candidate（validate_plan）
```
- **重写标注**：`【保留】`。

### `planning/service.py`（157 行）
- **职责**：Session-backed 变更边界。
- **对外 API**：`TaskPlanService(store, writer)`：`current()`、`create/update/revise(...)`；`TaskPlanMutation(plan, projection, changed, changes)`。
- **核心流程**：每个变更在 `_mutation_lock()`（线程锁 + `portalocker` 文件锁）下执行 reducer，成功后 `writer.append_task_plan_updated(previous_revision, operation, changes, snapshot)` 落库。
- **设计原理**：文件锁防多进程并发改同一 session 的 plan；事件里存完整已验证快照。
- **重写标注**：`【简化】`（TaskPlan 可选；文件锁可去掉）。

### `planning/validation.py`（35 行）
- **职责**：结构 + 执行状态校验。
- **对外 API**：`validate_plan(plan)`：id 唯一、无自依赖、无缺失依赖、拓扑无环、linear 最多一个 in_progress、in_progress 必须依赖全完成。
- **重写标注**：`【保留】`。

### `planning/__init__.py`（39 行）
- **职责**：导出领域类型与纯视图。刻意不含 agent/runtime import。
- **重写标注**：`【保留】`。

---

## 9. 上下文系统（context/ 全部）—— 本文档最大章节

### 9.1 总览

`context/` 是 FirstCoder 最复杂的包。它承担：**持久化事实账本（models/events/store）、事件写入（writer）、运行时状态（runtime_state/runtime_replay）、投影（context_builder）、压缩（compaction/llm_compact/manager/triggers/token_budget）、压缩产物存储（checkpoint/archive）、压缩内容算法（content/）、任务边界（task_boundary）**。

数据流总览：

```
[writer 追加事件] → [JSONL store] → [rebuild_session_view 重放] → SessionView
SessionView + budget + runtime_state
  → ContextBuilder.build_provider_messages → ChatMessage[]（发给 provider）
  → ContextWindowManager.compact_if_needed → CompactionPipeline(L1-L3) + LlmCompactService(L4)
       → 压缩替换写回（compaction_completed 事件）→ checkpoint/archive 落盘
  → 重放后新 view 反映压缩结果
```

### 9.2 预算与估算

### 📌 `context/token_budget.py`（108 行）—— 重点精读
- **职责**：上下文 token 预算的集中估算。
- **对外 API**：
  - `IMAGE_INPUT_TOKEN_ESTIMATE = 1024`。
  - `ContextBudget`（frozen）：`context_window, output_reserve, input_capacity, fixed_tokens, history_tokens, input_tokens, high_watermark, low_watermark, source`。
  - `estimate_text_tokens(text) -> int`：`max(1, (len+3)//4)`（字符数÷4 近似）。
  - `build_context_budget(*, messages, tools, context_window, max_output_tokens) -> ContextBudget`。
- **核心流程**：
```
resolved_window = context_window or DEFAULT_CONTEXT_WINDOW(200_000)
output_reserve = max_output_tokens or DEFAULT_OUTPUT_RESERVE(4096)
usable_window = window * 0.95
input_capacity = usable_window - output_reserve
fixed_tokens = system 消息 + 工具 schema token
history_tokens = 非 system 消息 token
high_watermark = input_capacity * 0.90
low_watermark = input_capacity * 0.72
```
- **设计原理**：刻意不绑定具体 tokenizer，用字符近似，避免 context 层过早依赖 provider。高低水位驱动压缩触发。
- **重写标注**：`【保留】`（若重写愿意接真实 tokenizer，这里就是替换点）。

### `context/budget_defaults.py`（4 行）
- **职责**：`DEFAULT_CONTEXT_WINDOW = 200_000`、`DEFAULT_OUTPUT_RESERVE = 4_096`。
- **重写标注**：`【保留】`。

### 9.3 投影管线

### 📌 `context/context_builder.py`（286 行）—— 重点精读
- **职责**：把内部会话事实投影成 provider 请求消息。**只投影，不压缩/总结/落盘/判断边界。**
- **对外 API**：`ContextBuilder.build_provider_messages(view, *, system_prefix=None, checkpoint=None, store_root=None) -> list[ChatMessage]`；`projected_tool_result_part_ids(view) -> tuple[str, ...]`；`InvalidCheckpointBoundaryError`。
- **核心流程**：
```
build_provider_messages：
  active_checkpoint = CheckpointIndex(view.checkpoints).latest()
  messages = system_prefix 拷贝
  if active_checkpoint: messages.append(user, checkpoint_summary_content)   # 旧历史摘要
  tail_messages = _tail_messages(view, checkpoint)
      # checkpoint 存在时从 tail_start_message_id 开始切片；tail 不能以 tool 消息开头
  tail = _collapse_identical_adjacent_duplicate_tool_calls(tail)  # 修复历史 bug 产生的重复
  validate_tool_call_sequence(tail)   # 投影前校验，坏序列直接报错
  if _has_trimmed_text(tail): messages.append(user, "[Earlier dialogue trimmed]")  # 聚合标记
  latest_user_id = latest_user_message_id(tail)
  for message in tail:
     projected = _project_message(message, preserve_trimmed_text=(id==latest_user_id), store_root)
     messages.extend(projected)

_project_message：
  role==system_meta → []（内部状态不发给 provider）
  role==tool → 每 part 若 kind in {tool_result, archive_placeholder} → ChatMessage(role="tool",
                content, name=tool_name, tool_call_id)
  role==assistant → 合并 text parts + ToolCall 列表 → ChatMessage(role="assistant")；
                fully trimmed 且无 tool_calls → 不发空消息
  role==user → _join_visible_text（过滤 compaction_state=="trimmed"）→ 加 [context: basis_message_id=...]
                前缀 → 投影 content_parts（图片从 session attachment store 读 base64，仅请求期）
```
- **与相邻模块的关系**：依赖 `context/checkpoint`、`context/models`、`context/tool_sequence`、`input/attachments`、`providers/types`。被 `agent/loop`、`agent/task_boundary_classifier` 依赖。
- **设计原理**：
  - 这是「事实账本 → 请求格式」的唯一投影点。checkpoint 不删除原始历史，只改变请求看到的上下文。
  - `basis_message_id` 锚点让 task_boundary 工具只能引用真实存在的消息 id。
  - 压缩把 part 标记为 `trimmed`，投影时过滤并放一个聚合标记，避免每条被遗忘的消息都加合成消息。
  - 图片 base64 只在请求构造时读取，JSONL 里只存路径与元数据。
- **隐藏的坑**：`validate_tool_call_sequence` 在投影前抛错意味着「压缩/checkpoint 不能切断 tool 配对」是硬约束。
- **重写标注**：`【保留】`。

### `context/tool_sequence.py`（55 行）
- **职责**：tool calling 历史序列校验。
- **对外 API**：`validate_tool_call_sequence(messages)`；`InvalidToolCallSequenceError`。
- **核心流程**：跟踪 pending tool_call_ids：assistant 消息先要求前序 pending 清空，再登记 tool_call；tool 消息要求 tool_call_id 在 pending 中；任何「孤立 tool_result」或「悬空 tool_call」都抛错。
- **重写标注**：`【保留】`。

### 9.4 lifecycle 分类

### 📌 `context/tool_lifecycle.py`（327 行）—— 重点精读
- **职责**：纯 lifecycle 分类，对 effective-tail 的 tool results 判定 FRESH/STALE/SUPERSEDED/DERIVED/DUPLICATE。
- **对外 API**：`ToolResultLifecycle(StrEnum)`；`ToolResultLifecycleRecord(message_id, part_id, lifecycle, reason, content_fingerprint, duplicate_of_part_id, source_targets)`；`SourceReadTarget(path, start_line, end_line, is_full_file)`；`index_tool_result_lifecycles(messages, *, current_turn=None) -> dict[(message_id, part_id), record]`。
- **核心流程**：
```
index_tool_result_lifecycles：
  建立 tool_call 索引（call_id → (name, arguments)）
  for tool 消息的每个 tool_result part：
    call = _call_for_result(...)（call_id 回溯；name 必须匹配）
    默认 lifecycle = DERIVED（derived_tool_output）
    若 ok != True → FRESH（失败结果不是 read/mutation 证据）
    tool_name == view → FRESH + source_targets（从 data.path/start_line/end_line/total_lines 解析）
    tool_name == read_multi → FRESH + 多文件 targets
    有 targets → 把被覆盖的早期 read 标记 SUPERSEDED
    tool_name in {write,edit,delete,apply_patch} 且 ok → 把该路径的 read 标记 STALE
  最后 _mark_derived_duplicates：内容指纹相同的最新 DERIVED 保留，其余标记 DUPLICATE
```
- **设计原理**：deliberately 只解释内置读写工具的结构化成功结果；不碰文件系统、不改状态，可安全重放。`current_turn` 参数保留但当前 phase 未用。
- **重写标注**：`【保留】`（L2/L3 压缩的决策依据）。

### 9.5 L1-L3 压缩 pipeline

### 📌 `context/compaction.py`（785 行）—— 重点精读
- **职责**：L1-L3 程序化上下文压缩 pipeline。
- **对外 API**：
  - `CompactionLevel = Literal["l1","l2","l3"]`。
  - `CompactionRequest`：`view, active_task_hash, target_tokens, current_turn, estimate_tokens, consumed_tool_result_part_ids, enabled_levels, required_levels, l2_result_target_tokens, force_route_current_text, force_old_task_compaction`。
  - `CompactionEvent`：`input_fingerprint, before_tokens, after_tokens, levels_attempted, stopped_at, changed_parts, reason, target_tokens, source_part_ids, output_part_ids, replacements, checkpoint_id, strategy_version, event_version, llm_used, success, error, created_at, noop, deduped, lifecycle_counts, level_metrics, archive_ids`。
  - `CompactionResult(view, event)`。
  - `CompactionPipeline(root, large_tool_result_tokens=1200, cold_turn_distance=8, cold_preview_chars=160)`：`compact(request)`。
- **核心流程**：
```
compact(request)：
  view = clone(request.view)；input_fingerprint = session_view_fingerprint
  before_tokens = estimate_tokens(view)
  lifecycle_records = index_tool_result_lifecycles(effective_tail, current_turn)
  required_levels = request.required_levels ∩ enabled_levels
  per_result_target = l2_result_target_tokens or large_tool_result_tokens

  早退：before <= target 且无 force 且无 required 且无 L3 强制/压力 → noop 事件返回
  循环 enabled_levels：
    level_replacements = _apply_level(view, level, lifecycle_records)
    after = estimate_tokens(view)
    若 after <= target 且剩余 required 为空 且无 L3 强制/压力 → 停在当前 level
  return CompactionResult(view, event)

_apply_l1（trim 旧任务普通对话）：
  只处理 user/assistant 的 text part；跳过 latest_user_id；跳过含 tool_call 的 assistant；
  is_old_task_part(part, active_task_hash)（metadata.task_hash != active_task_hash 且未压缩）
  且 _is_cold_old_task_part（created_turn 距 current_turn >= cold_turn_distance，除非 force）
  → compact_old_task_part(part)（content 置空，metadata.compaction_state="trimmed"）

_apply_l2（route 压缩 DERIVED tool result）：
  对每个 part：_should_route_compact_l2_part（已消费 + lifecycle==DERIVED + 未压缩 + 非检索保护）
  router.compact_part(part) → 若压缩后有收益：先 archive.store_original（存原始字节），
  再替换 part 并写 metadata（archive_id/compaction_state="l2_route_compacted"/lifecycle...）
  _replace_if_smaller（必须严格更小才替换）

_apply_l3（把过大/过期 tool result 换成 archive placeholder）：
  _l3_candidates() 排序（priority: DUPLICATE<SUPERSEDED<STALE<over_target<DERIVED；
    同 priority 按 -tokens, created_turn, tail_index）
  for candidate: 若非 mandatory 且非 over_target 且已 in budget → break
    _can_archive_l3_part（已消费 + lifecycle in {STALE,SUPERSEDED,DUPLICATE,DERIVED} +
      compaction_state in {raw, l2_route_compacted} + 非检索保护）
    record = _l3_backing_record（有 archive_id 用原记录，否则 store_original）
    compacted = archive.make_placeholder(part, record, lifecycle, summary, key_errors)
    _replace_if_smaller → changed
```
- **与相邻模块的关系**：依赖 `context/archive`、`checkpoint`、`content/*`（路由压缩器）、`identity`、`models`、`token_budget`、`tool_lifecycle`、`versions`。被 `context/manager` 依赖。
- **设计原理**：
  - **L1 = 刻意遗忘**（旧任务普通对话置空），不是小摘要。
  - **L2 = 路由压缩 + 先归档**：DERIVED 结果按内容类型（diff/build/json/code/html/search/plain）压缩，压缩前把原始字节存 archive。
  - **L3 = 归档换占位**：把大/过期结果换成 `[Tool result archived]` 占位，原始内容可 `retrieve_archive` 找回。
  - `_effective_tail_messages` 只处理 latest checkpoint 之后的真实 tail，与 ContextBuilder 的 effective context 边界一致。
  - `noop` 指纹去重（`_seen_noop_fingerprints`）防止反复无效果压缩。
- **重写标注**：`【保留】`。

### 9.6 checkpoint / archive

### 📌 `context/checkpoint.py`（92 行）—— 重点精读
- **职责**：checkpoint 数据结构与 latest 选择。
- **对外 API**：`Checkpoint`（`id, session_id, summary, tail_start_message_id, covered_until_message_id, source_fingerprint, created_at, sequence, strategy_version, metadata`）；`CheckpointIndex(checkpoints)`：`latest()`；`checkpoint_summary_content(checkpoint)`。
- **核心流程**：`latest()` = `max(checkpoints, key=(sequence, created_at, id))`。
- **设计原理**：checkpoint 只记录「旧历史摘要 + tail 起点」，不生成摘要、不自动移动边界。
- **重写标注**：`【保留】`。

### 📌 `context/archive.py`（311 行）—— 重点精读
- **职责**：压缩工具结果的持久化、内容寻址存储与占位构造。
- **对外 API**：`ArchiveRecord(archive_id, session_id, content_sha256, original_chars, original_tokens, created_at, schema_version)`；`ToolResultArchive(root)`：`store_original(session_id, part, original_content=None)`、`read(session_id, archive_id) -> (record, raw)`、`make_placeholder(part, record, lifecycle="derived", summary=None, key_errors=())`；`ArchiveIntegrityError`。
- **核心流程**：
```
store_original：digest = sha256(content)；archive_id = f"ar_{digest[:32]}"；_store 原子写 .txt + .json
read：读 txt + json；校验 schema_version / archive_id / content_sha256 / chars / id 一致性
make_placeholder：构造 ≤480 字符的占位文本
  [Tool result archived] / archive_id / tool / status / lifecycle / original_tokens /
  summary / key_errors / Use retrieve_archive(...)
  metadata：archive_id, original_content_sha256, original_tokens,
            compaction_state="archived", compacted_by="l3_archive"
```
- **设计原理**：archive 只拥有「磁盘字节 + 两种占位格式」，不做「何时压缩」的策略决策。内容寻址保证不可变；重存相同内容 no-op；既有文件 digest 不同 = 损坏（拒绝覆盖）。调用方拿到的是 path-free 的 `(record, raw)`，路径不外泄。
- **重写标注**：`【保留】`。

### 9.7 LLM 压缩（L4）

### 📌 `context/llm_compact.py`（446 行）—— 重点精读
- **职责**：L4 LLM compact 的 MVP 实现。
- **对外 API**：
  - `CODING_HANDOFF_HEADINGS`（7 个固定标题：当前目标/已知事实与硬约束/已确认的决定及理由/相关文件与当前实现状态/已运行命令及有效结果/当前错误与未解决事项/下一步）。
  - `PromptTooLongError / CompactTimeoutError / NoSummaryError / InvalidLlmCheckpointBoundaryError / UnconsumedLlmCheckpointBoundaryError / LlmSourceFingerprintMismatchError`。
  - `LlmCompactSummary(summary, tail_start_message_id, covered_until_message_id)`。
  - `LlmCompactSummarizer`（Protocol：`summarize(messages, *, summary_mode)`）。
  - `LlmCompactRequest`：`view, runtime_state, consumed_tool_result_part_ids, mode, expected_source_fingerprint, summary_mode`。
  - `LlmCompactEvent`：`status, source_fingerprint, retry_count, failure_reason, checkpoint_id, fallback_steps, final_failure_reason`。
  - `LlmCompactCandidate(checkpoint, event)`。
  - `LlmCompactService(store, summarizer, retry_policy, auto_failure_limit=3)`：`generate_candidate(request)`、`commit_candidate(candidate, *, runtime_state)`。
  - `normalize_coding_handoff(summary) -> str`。
- **核心流程**：
```
generate_candidate(request)：
  source = _build_l4_source(view)  # 只取会话历史（排除 system_meta），若有 checkpoint 则
    # 把 checkpoint summary 作为第一条 user 消息 + tail 消息
  source_fingerprint = hash(session_id, strategy_version, base_checkpoint_id, tail ids, messages)
  若 expected != 当前 → raise LlmSourceFingerprintMismatchError
  若 runtime_state.last_compaction_input_fingerprint == source → skipped(duplicate_source)
  若 mode==auto 且 auto_compact_circuit_is_open → skipped(circuit_open)
  loop（attempts++）：
    summary = summarizer.summarize(source_messages, summary_mode)
    _validate_summary_boundary(summary, source, consumed_part_ids)
      # tail_start/covered_until 必须在合法 tail 内；covered 必须在 tail_start 之前；
      # 校验 tool_call 序列；不能覆盖未消费 tool 事务（UnconsumedLlmCheckpointBoundaryError）
    checkpoint = _candidate_checkpoint(...)  # sequence = max+1；metadata 记 created_by/source
    return success
  异常 → retry_policy.decide(reason, attempt)：prompt_too_long/timeout/no_summary 有限重试
commit_candidate(candidate, runtime_state)：
  store.append_event(checkpoint_created, checkpoint.to_dict())
  runtime_state.latest_checkpoint_id = checkpoint.id
  runtime_state.last_compaction_input_fingerprint = event.source_fingerprint
normalize_coding_handoff(summary)：把模型输出的散文归一化到固定 7 标题；未知 Markdown 标题
  转正文；缺节写「无」
```
- **与相邻模块的关系**：依赖 `context/checkpoint/events/identity/models/retry_policy/runtime_state/store/tool_sequence/versions`。被 `context/manager` 依赖。
- **设计原理**：让模型只生成摘要正文，**checkpoint 边界由本地程序选择并校验**，避免把恢复边界完全交给模型。L4 摘要只看会话历史，不混入 system prompt/工具 schema。
- **重写标注**：`【保留】`（若重写需要 L4；否则可延后）。

### `context/provider_summarizer.py`（129 行）
- **职责**：用通用 `ChatProvider` 实现 L4 摘要器适配。
- **对外 API**：`ProviderLlmCompactSummarizer(provider, *, max_tokens=1200)`：`summarize(messages, *, summary_mode) -> LlmCompactSummary`。
- **核心流程**：`_tail_boundary(messages)` 从后往前选合法 tail（校验 tool 序列）；`_build_summary_prompt` 组装 7 标题指令 + 历史文本；provider.complete；ProviderError 映射（PROMPT_TOO_LONG→PromptTooLongError 等）。
- **重写标注**：`【保留】`。

### `context/retry_policy.py`（52 行）
- **职责**：L4 compact 有限重试策略。
- **对外 API**：`CompactRetryPolicy(max_prompt_too_long_retries=1, max_timeout_retries=2, max_no_summary_retries=1)`：`decide(reason, *, attempt) -> CompactRetryDecision(should_retry, action, reason)`。
- **重写标注**：`【保留】`。

### `context/fallback.py`（36 行）
- **职责**：LLM compact 失败后的有限兜底。
- **对外 API**：`CompactFallbackPolicy.action_for(reason) -> FallbackAction`：prompt_too_long→stronger_programmatic；timeout/no_summary→retry_l4_stronger_summary；其他→fail。`FallbackStep` 记录单步。
- **重写标注**：`【保留】`。

### 9.8 manager 编排

### 📌 `context/manager.py`（618 行）—— 重点精读
- **职责**：上下文窗口压缩触发编排，用一次 provider-facing budget 编排 L1-L4 + fallback。
- **对外 API**：
  - `ContextWindowTrigger(StrEnum)`：AUTO/TASK_HASH_CHANGED/PROMPT_TOO_LONG/MANUAL。
  - `ContextCompactMode`：AUTO/MANUAL。
  - `ProgrammaticCompactor` Protocol（`compact(request)`）；`L4Compactor` Protocol（`generate_candidate`/`commit_candidate`）。
  - `ContextCompactRequest`：`view, runtime_state, budget, estimate_budget, trigger, mode, current_turn, target_tokens`。
  - `ContextCompactResult`：`status(success|skipped|failed), reason, view, before_tokens, after_tokens, programmatic_event, l4_event, fallback_steps, final_failure_reason`。
  - `ContextWindowManager(store, pipeline=None, l4_service=None, config=None, fallback_policy=None)`：`compact_if_needed(request)`。
- **核心流程**：
```
compact_if_needed(request)：
  trigger/mode 归一化；before_tokens = budget.input_tokens
  decision = evaluate_context_triggers(view, config, input_tokens, high, low)
  AUTO 且 under_threshold → skipped(under_threshold)
  AUTO 且 auto_compact_circuit_is_open → skipped(circuit_open)
  AUTO 且 last_no_effect_compaction_fingerprint == 当前 fingerprint → skipped(skipped_no_effect)
  target_tokens = request.target_tokens or (TASK_HASH_CHANGED ? low*2//3 : low)
  if budget.fixed_tokens >= budget.low_watermark → failed(fixed_context_over_budget)
  required_levels = (TASK_HASH_CHANGED → ("l2","l3") else ())
  programmatic = pipeline.compact(CompactionRequest(...))
  after_tokens = estimate_budget(programmatic.view).input_tokens
  记录 programmatic 事件
  if after < target and trigger != PROMPT_TOO_LONG → success
  if l4_service is None → final_failure(l4_service_missing)
  outcome = _generate_validate_commit(LlmCompactRequest(view=programmatic.view, ...))
  if outcome 非 success → _run_fallback
  记录 l4 事件；_record_auto_success_if_needed；return success

_generate_validate_commit：
  candidate = l4_service.generate_candidate(l4_request)
  if 非 success → 标 failed（unconsumed_boundary→unconsumed_result_over_budget 若 over capacity）
  candidate_view = view + checkpoint
  try candidate_budget = estimate_budget(candidate_view)
  except InvalidCheckpointBoundary/InvalidToolCallSequence → failed(invalid_tool_sequence)
  if candidate_budget.input_tokens >= target → failed(still_over_budget)
  l4_service.commit_candidate(candidate, runtime_state)
  rebuilt_view = store.rebuild_session_view(...)；return 成功

_run_fallback（按 fallback_policy.action_for(reason)）：
  stronger_programmatic → 再跑一次更强 L1-L3（force_route_current_text / force_old_task）
  retry_l4_stronger_summary → 用 summary_mode="stronger" 再 generate_validate_commit
  每步记录 FallbackStep；成功/失败都返回结构化结果
```
- **与相邻模块的关系**：依赖 `context/checkpoint/compaction/context_builder/fallback/identity/llm_compact/models/runtime_state/store/token_budget/tool_sequence/triggers/writer`。被 `agent/loop`（经 `ContextManagerLike` Protocol）、`app/commands`（手动 compact）依赖。
- **设计原理**：manager 是「策略决策层」，pipeline 是「执行层」，l4_service 是「LLM 摘要层」。loop 只发 ContextCompactRequest，manager 决定是否/如何压缩。自动压缩失败有熔断（`runtime_state.auto_compact_failure_count`，3 次失败禁用 30 分钟）。
- **重写标注**：`【保留】`。

### `context/triggers.py`（51 行）
- **职责**：非窗口配置与动态触发判断。
- **对外 API**：`ContextCompactionConfig`（`l2_result_target_tokens=800, large_tool_result_tokens=1200, max_turn_tool_result_tokens=4000, max_tail_messages=120, cold_turn_distance=8, cold_preview_chars=160`）；`ContextTriggerDecision`；`evaluate_context_triggers(view, config, *, input_tokens, high_watermark, low_watermark)`。
- **核心流程**：普通 AUTO 只看 `input_tokens >= high_watermark`；低于则 under_threshold。
- **重写标注**：`【保留】`。

### 📌 `context/runtime_state.py`（149 行）—— 重点精读
- **职责**：会话运行期状态（不该塞进自然语言消息的状态）。
- **对外 API**：`SessionRuntimeState`：`session_id, active_task_hash, candidate_task_hash, candidate_task_basis_message_id, task_hash_stable_count, latest_checkpoint_id, auto_compact_failure_count, auto_compact_disabled_until, last_auto_compact_failure_reason, system_prompt_fingerprint, last_compaction_input_fingerprint, last_no_effect_compaction_fingerprint, consumed_tool_result_part_ids, recent_compaction_events`。
  - 方法：`observe_task_hash_candidate(candidate_hash, *, required_stable_count=2) -> bool`（稳定后切换 active hash）、`record_auto_compact_failure(reason, *, failure_limit=3, disabled_minutes=30) -> bool`、`record_auto_compact_success()`、`record_compaction_event(entry, *, limit=10)`。
  - 模块函数：`active_auto_compact_disabled_until(state)`、`auto_compact_circuit_is_open(state)`。
  - `CompactionHistoryEntry`。
- **设计原理**：task hash 采用「候选 + 稳定计数」机制降低模型输出抖动误触发；压缩熔断用带时区的 UTC ISO 时间。
- **重写标注**：`【保留】`。

### `context/runtime_replay.py`（137 行）
- **职责**：从 JSONL 事件恢复运行期状态。
- **核心流程**：`replay_runtime_state(store, session_id)`：遍历事件，`provider_projection_consumed` → 累计 consumed_tool_result_part_ids；`task_boundary_observed` → 恢复 active/candidate hash；`checkpoint_created`/`compaction_completed`/`llm_compaction_completed` → 恢复 latest_checkpoint、fingerprint、失败计数；`compaction_skipped` → last_no_effect。
- **重写标注**：`【保留】`。

### 9.9 writer / store

### 📌 `context/writer.py`（405 行）—— 重点精读
- **职责**：会话事件写入 helper。JSONL store 底层只负责 append/list/rebuild；writer 把常见事件写入集中起来。
- **对外 API**：`SessionEventWriter(store, session_id, current_turn=0)`：
  - `append_event(event_type, payload)`。
  - `append_session_created(**metadata)`、`append_session_metadata_updated(**metadata)`。
  - `append_agent_turn_telemetry(payload)`。
  - `append_message_part_metadata_updated(*, message_id, part_id, metadata)`。
  - `append_provider_projection_consumed(*, request_id, projection_fingerprint, part_ids, provider, model)`。
  - `append_user_message(content, *, attachments=None, metadata=None, part_metadata=None) -> str`（**current_turn += 1**）。
  - `append_assistant_response(response) -> str`、`append_assistant_parts(parts, *, metadata, message_id) -> str`。
  - `append_tool_result(*, tool_call, result) -> str`、`append_tool_result_part(part, *, message_id) -> str`。
  - `append_compaction_completed(*, trigger, target_tokens, event)`、`append_llm_compaction_completed(...)`、`append_compaction_skipped(...)`。
  - `append_task_boundary_observation(observation)`。
  - `append_task_plan_updated(*, previous_revision, operation, changes, snapshot)`（校验 revision 链）。
  - `append_background_notification(...)`（不递增 turn）。
  - `tool_call_to_part(*, message_id, tool_call)`。
- **核心流程**：所有消息事件统一走 `_part_metadata`（给每个 part 补 `created_turn` / `turn_id`），保证上下文窗口判断需要的字段不遗漏。
- **设计原理**：writer 是所有消息事件落库前的最后一层公共入口，turn 元数据在此统一补齐，避免直接调用 store 的路径漏字段。
- **重写标注**：`【保留】`。

### 📌 `context/store.py`（193 行）—— 重点精读
- **职责**：基于 JSONL 的会话事件存储。
- **对外 API**：`JsonlSessionStore(root)`：`append_event(event)`、`list_events(session_id)`、`rebuild_session_view(session_id) -> SessionView`；`SessionStoreCorruptError`。
- **核心流程**：
```
append_event：写 `<root>/sessions/<session_id>.jsonl`（sort_keys 保证稳定行序）；
  然后 SessionIndex(root).update_event(event)（同步更新列表索引）
rebuild_session_view：遍历事件，_apply_event：
  session_created/metadata_updated → merge metadata
  checkpoint_created → view.checkpoints.append
  compaction_completed → _apply_compaction_replacements（按 message_id+source_part_id 替换 part）
  message_part_metadata_updated → 更新 part.metadata
  task_plan_updated → 解析 + 校验 revision 链 → view.task_plan
  其余（user/assistant/tool/background_notification）→ 按 EVENT_ROLE_MAP 追加 AgentMessage
```
- **与相邻模块的关系**：被 `writer`、`agent/session`、`context/manager`、`session/*`、`app/factory` 依赖。
- **设计原理**：JSONL 让 resume、压缩事件、调试记录都人工可读；注释明确「迁移 SQLite 时保留 append_event/list_events/rebuild_session_view 边界」。store 的 `_apply_event` 是事件重放的唯一解释器。
- **隐藏的坑**：`task_plan_updated` 重放时校验 revision 链，损坏会抛 `SessionStoreCorruptError`——这是 schema 边界。
- **重写标注**：`【保留】`。

### `context/events.py`（42 行）
- **职责**：append-only 会话事件模型。
- **对外 API**：`SessionEvent(id, session_id, type, payload, created_at)`；`from_dict/to_dict`。
- **重写标注**：`【保留】`。

### `context/identity.py`（88 行）
- **职责**：ID 与稳定指纹工具。
- **对外 API**：`new_session_id/message_id/part_id/event_id/request_id/checkpoint_id`（`前缀_uuid4hex[:12]`）；`stable_json_hash(value, *, length=16)`（sort_keys + 紧凑分隔符，跨运行稳定）；`content_fingerprint(text, *, length=16)`；`session_view_fingerprint(view)`。
- **重写标注**：`【保留】`。

### `context/metadata.py`（30 行）
- **职责**：metadata patch helper。
- **对外 API**：`merge_metadata_patch(current, patch)`（`None` 不删除已有值）；`metadata_without_reserved_keys(metadata)`（保护 session_id）。
- **重写标注**：`【保留】`。

### `context/versions.py`（8 行）
- **职责**：策略版本常量。`SYSTEM_PROMPT_VERSION="v18"`、`COMPACTION_STRATEGY_VERSION="v2"`、`ARCHIVE_SCHEMA_VERSION="v2"`、`TASK_BOUNDARY_TOOL_VERSION="v1"`、`CHECKPOINT_STRATEGY_VERSION="v1"`、`CONTEXT_EVENT_SCHEMA_VERSION="v2"`。
- **重写标注**：`【保留】`。

### `context/inspector.py`（137 行）
- **职责**：上下文调试视图（TUI `/context`、`/compact status`）。
- **对外 API**：`ContextInspector.inspect(view, runtime, *, budget) -> ContextInspectionReport`；`ContextInspectionReport`（大量只读字段）；`TailInspection`。
- **重写标注**：`【保留】`（调试入口）。

### `context/system_prompt.py`（136 行）
- **职责**：稳定系统前缀构造与缓存。
- **对外 API**：`SystemPromptInputs`（`base_rules, agents_md, provider_name, provider_capabilities, permission_policy, skill_protocol, skill_catalog_summary, benchmark_task, mode, prompt_version`）；`PromptPrefixCacheEntry(fingerprint, messages)`；`SystemPromptBuilder.fingerprint/build`；`PromptPrefixCache.get_or_build`。
- **核心流程**：fingerprint 由稳定输入 hash 得到；build 拼 base_rules + agent_instructions（按 benchmark 与否选 `prompts/agent_instructions.md` 或 `benchmark_agent_instructions.md`）+ project instructions + skill protocol/catalog + provider + permission policy。
- **设计原理**：系统提示词属于请求配置，不属于普通会话事实。cache 只缓存最近一次 prefix。
- **重写标注**：`【保留】`。

### `context/task_boundary.py`（305 行）—— 重点精读
- **职责**：任务边界观察与程序生成 task hash。
- **对外 API**：
  - `TaskBoundaryDecision(StrEnum)`：SAME/NEW/UNCERTAIN。
  - `TaskBoundaryObservation`：`decision, basis_message_id, candidate_hash, confirmed_change, should_trigger_compaction, stable_count, active_task_hash, candidate_basis_message_id, triggered_compaction, confirmation_reason, required_stable_count, event_version, strategy_version, created_at`。
  - `TaskBoundaryPolicy(single_observation_basis_message_ids)`。
  - `TaskBoundaryService(*, required_stable_count=2, known_message_ids=None, policy=None)`：`candidate_hash(*, session_id, basis_message_id)`、`observe(state, *, decision, basis_message_id)`、`to_event(...)`、`initialize_active_task(state, *, basis_message_id)`。
  - `observation_from_tool_result_data(data)`。
- **核心流程**：
```
observe(state, decision, basis_message_id)：
  decision==SAME 且已有 candidate → 复用 candidate_hash；observe_task_hash_candidate
    （稳定计数达到 required_stable_count → confirmed_change=True）
  decision in {SAME, UNCERTAIN}（无 candidate）→ 重置 candidate，不触发
  decision==NEW：
    candidate_hash = stable_json_hash({basis_message_id, session_id, version}, 16) → "task_<hash>"
    active 为空 → 直接设为 active（initial_task）
    否则 observe_task_hash_candidate（同 hash 计数 +1，达到 N 才确认切换）
  confirmed_change → should_trigger_compaction=True
initialize_active_task：active 为空时直接用 basis_message_id 生成初始 hash（不依赖模型工具调用）
```
- **设计原理**：模型只提交 decision + basis_message_id，hash 由程序用稳定输入生成，避免模型输出格式抖动。稳定计数（默认 2 次）降低误触发。
- **重写标注**：`【保留】`。

### `context/content/` 子包（L2 内容路由压缩器）

### `context/content/router.py`（178 行）—— 重点精读
- **职责**：L2 内容路由压缩框架：识别类型 → 分发压缩器 → 验证收益 → 统一写 metadata。
- **对外 API**：`RouteContentType(Enum)`（SEARCH_RESULTS/GIT_DIFF/BUILD_OUTPUT/JSON_ARRAY/JSON_OBJECT/SOURCE_CODE/HTML/PLAIN_TEXT）；`RouteDetection(content_type, confidence, metadata)`；`RouteContext(detection, preview_chars)`；`RouteCompactResult(content, content_type, compacted_by, metadata)`；`RouteCompressor` Protocol；`RouteCompactRouter(compressors, min_original_tokens=40, preview_chars=160)`：`compact_part(part)`；`detect_route_content_type(content, *, tool_name=None)`。
- **核心流程**：`compact_part`：tokens 低于阈值 → None；`detect_route_content_type`（tool_hint 优先：grep→search、git_diff→diff；其次 JSON 解析；再 diff/html/search/code/build 正则）→ 找压缩器（无则 fallback PLAIN_TEXT）→ 压缩结果必须严格更小 → 写 metadata（original_tokens/replacement_tokens/content_fingerprint/compaction_state="route_compacted"/compacted_by/compacted_at/content_type/detected...）。
- **重写标注**：`【保留】`（L2 核心；具体压缩算法可增删）。

### `context/content/compressors.py`（94 行）
- **职责**：确定性内容压缩器。`compact_old_task_part`（L1 trimmed 表示）；`PlainTextRouteCompressor`（保留首尾 + token 元数据）。
- **重写标注**：`【保留】`。

### `context/content/detector.py`（28 行）
- **职责**：`is_already_compacted(part)`（compaction_state ∈ {archived,trimmed,micro_compacted,route_compacted,l2_route_compacted,checkpointed,pinned}）；`is_old_task_part(part, *, active_task_hash)`。
- **重写标注**：`【保留】`。

### `context/content/code.py`（156 行）
- **职责**：source_code 压缩器。保留 import/type/signature/TODO/ERROR 行 + 签名后 2 行 body；最多 120 行；识别语言（python/ts/js/go/rust/c）。
- **重写标注**：`【简化】`。

### `context/content/build.py`（152 行）
- **职责**：build_output/shell log 压缩器。保留 error 块（首尾 + 栈上下文）、warning、summary 行。
- **重写标注**：`【简化】`。

### `context/content/diff.py`（107 行）
- **职责**：git_diff 压缩器。保留 diff 头、@@、+/- 行，上下文只留前 2 行，最多 20 个文件。
- **重写标注**：`【简化】`。

### `context/content/html.py`（182 行）
- **职责**：html 压缩器。HTMLParser 提取 title/headings/文本块/链接；跳过 script/style/svg/canvas；按关键词打分选块。
- **重写标注**：`【简化】`。

### `context/content/json.py`（220 行）
- **职责**：json_array/json_object 压缩器。保留首尾 + 高价值 key/值；嵌套值摘要；`_compact` 元数据包装。
- **重写标注**：`【简化】`。

### `context/content/search.py`（130 行）
- **职责**：search_results/grep 压缩器。按文件分组，每文件保留首尾 + 高价值匹配，最多 15 文件 × 5 匹配。
- **重写标注**：`【简化】`。

### `context/content/__init__.py`（1 行）
- **职责**：docstring 占位。
- **重写标注**：`【保留】`。

### `context/prompts/agent_instructions.md`（56 行）与 `benchmark_agent_instructions.md`（78 行）
- **职责**：两份系统提示词正文。前者是交互版角色/工作循环/工具使用/TaskPlan 纪律/验证完成/沟通；后者是 benchmark 版（非交互、任务即规范、验收证据、不得削弱 verifier）。
- **设计原理**：benchmark 版严格禁止交互、禁止改动 verifier、要求失败敏感断言、任务完成后立即停止。
- **重写标注**：`【必须改】`（prompt 文案重写时必然要重写；结构（分交互/非交互两版）可保留）。

### `context/__init__.py`（1 行）
- **职责**：docstring 占位。
- **重写标注**：`【保留】`。

---

## 10. MCP 层（mcp/ 全部）

### `mcp/models.py`（64 行）
- **职责**：MCP 配置与运行状态数据模型。
- **对外 API**：`McpConfigError`；`McpLocalServerConfig(name, command, env, enabled, timeout_ms, allowed_tools)`；`McpRemoteServerConfig(name, url, headers, bearer_token_env_var, enabled, timeout_ms, allowed_tools)`；`McpServerStatus(name, state, tool_count, error)`；`McpToolDescription(name, description, input_schema)`。frozen + MappingProxyType 防变。
- **重写标注**：`【保留】`。

### `mcp/config.py`（149 行）
- **职责**：MCP TOML 配置提取与校验。
- **对外 API**：`load_mcp_configs(app_config)`；`resolve_environment_placeholders(value, env)`（`{env:NAME}` 占位符，缺失抛错不泄露值）。
- **重写标注**：`【保留】`。

### 📌 `mcp/manager.py`（259 行）—— 重点精读
- **职责**：同步 FirstCoder 与异步 MCP SDK 之间的连接协调器。
- **对外 API**：`McpManager(configs, transport_factory=None, environment=None, retry_attempts=3, retry_delay_seconds=1.0)`：`connect_all()`、`connect_all_in_background()`、`reconnect(name=None)`、`statuses()`、`doctor(name)`、`tools() -> tuple[(server, McpToolDescription)]`、`call_tool(server, tool, arguments)`、`close()`。
- **核心流程**：
```
__init__：每个 config 建初始 status；asyncio.new_event_loop + 守护线程 _run_loop(run_forever)
connect_all：每个启用 server 一个线程 _connect_one；join
_connect_one：重试 3 次；resolve_environment_placeholders → transport_factory.create →
  _submit(_initialize(transport), timeout) → 成功则存 transport/catalog（按 allowed_tools 过滤）
  → status=connected；失败 → status=failed(error)
call_tool：_submit(transport.call_tool(tool, arguments), config.timeout_ms)
  # asyncio.run_coroutine_threadsafe + future.result(timeout) 桥接同步/异步
close：取消 pending futures；关 transports；loop.stop()
```
- **设计原理**：用守护线程跑事件循环，同步层用 `run_coroutine_threadsafe` 桥接；后台并行连接避免阻塞 TUI 首帧。
- **重写标注**：`【保留】`（若重写需要 MCP；否则 `【暂缓】`）。

### `mcp/transport.py`（127 行）
- **职责**：官方 MCP SDK 传输适配（stdio / Streamable HTTP）。
- **对外 API**：`McpTransport` Protocol；`McpTransportFactory`；`SdkMcpTransportFactory.create(config)`。
- **重写标注**：`【保留】`。

### `mcp/adapter.py`（134 行）
- **职责**：把发现的 MCP 工具转换为 FirstCoder 同步 Tool。
- **对外 API**：`adapt_mcp_tool(manager, server, discovered_tool, *, existing_names=None) -> Tool`。
- **核心流程**：`name = f"mcp__{server}__{tool}"`；schema 校验；`execute(**arguments)` → `manager.call_tool` → 结果转 `ToolResult`（content 字段 / structuredContent / isError）；permission = `MCP_TOOL` 动作，target=`server/tool`，`allow_auto=False`。
- **重写标注**：`【保留】`。

### `mcp/search.py`（116 行）
- **职责**：MCP 工具本地搜索（初始 schema 集未暴露的工具）。
- **对外 API**：`search_mcp_tools(entries, query)`；`create_mcp_tool_search(entries)`。
- **核心流程**：token 打分（exact name 1w / name token 100 / server token 20 / description 1），返回前 8；工具结果带 `mcp_tool_search.activated_tools`，loop 据此激活对应工具（`_observe_mcp_search_result`）。
- **重写标注**：`【暂缓】`。

### `mcp/config_store.py`（149 行）
- **职责**：MCP 配置文件保真读写（CLI `mcp add/remove` 用）。
- **对外 API**：`McpConfigStore(path)`：`add_local/add_remote/remove/list_servers`。用 tomlkit 保留其他配置。
- **重写标注**：`【暂缓】`。

### `mcp/__init__.py`（20 行）
- **职责**：导出 MCP 配置与模型类型。
- **重写标注**：`【保留】`。

---

## 11. 工具层（tools/ 全部）

### 11.1 工具抽象与注册

### 📌 `tools/types.py`（79 行）—— 重点精读
- **职责**：工具层共享类型。
- **对外 API**：
  - `ToolResult(name, ok, content, data, error)`。
  - `ToolExecutor` Protocol（`__call__(**kwargs) -> ToolResult`）。
  - `ToolPermissionSpec(action, target_arg=None, target_value=None, target_builder=None, cwd_arg=None, reason="", allow_always=True, allow_auto=True)`。
  - `Tool(definition, executor, permission=None)`；`name` property。
  - `make_error_result(name, message, **data)`、`make_text_result(name, content, **data)`。
- **重写标注**：`【保留】`。

### 📌 `tools/registry.py`（81 行）—— 重点精读
- **职责**：工具注册与执行入口。
- **对外 API**：`ToolRegistry(tools=None)`：`register(tool)`（同名拒绝）、`definitions()`、`names()`、`tools()`、`get(name)`、`execute(name, arguments=None) -> ToolResult`。
- **核心流程**：`execute`：未知工具/参数非 dict/TypeError/Exception 全部转成 `ToolResult` 失败结果，**绝不抛异常打断 loop**。
- **重写标注**：`【保留】`。

### `tools/session_registry.py`（111 行）
- **职责**：会话级工具注册表工厂。
- **对外 API**：`create_session_tool_registry(*, session_id, runtime_state, tools, known_message_ids, single_observation_basis_message_ids, task_boundary_required_stable_count, permission_manager, archive_root, current_turn, store, writer, skill_catalog) -> ToolRegistryLike`。
- **核心流程**：注入 `task_boundary`（依赖 runtime_state）、`task_create/update/revise/list`（需 store+writer 构造 TaskPlanService）、`load_skill`、`retrieve_archive`（session 绑定）；`permission_manager` 存在时包 `PermissionAwareToolRegistry`。保留名冲突直接抛错。
- **重写标注**：`【保留】`。

### 📌 `tools/permission_registry.py`（167 行）—— 重点精读
- **职责**：权限感知工具注册表 wrapper。
- **对外 API**：`PermissionAwareToolRegistry(registry, permission_manager)`：代理 register/definitions/names/tools/get/execute；`preflight(name, arguments)`；`execute_without_permission_check(name, arguments)`；`permission_request_for_tool(tool, arguments)`。
- **核心流程**：
```
execute：preflight → None（无权限声明）→ 直接执行
  DENY → make_permission_denied_result
  ASK → build_confirmation → make_permission_confirmation_result（带 requires_user_input）
  ALLOW → 直接执行
preflight：构造 PermissionRequest（id = perm_<tool>_<sha256(arguments)>>[:12]）→ manager.preflight
execute_without_permission_check：执行已确认的 pending tool，不再次触发 ASK
```
- **重写标注**：`【保留】`。

### `tools/builtin.py`（88 行）
- **职责**：内置工具集合。`create_builtin_registry(root, include_mutation_tools, include_execution_tools, include_network_tools, access, include_ask_user, include_think, include_web_search, process_manager)`。
- **核心流程**：默认只注册只读工具；写入/执行/网络工具必须显式启用。最后 `apply_agent_tool_description` 统一替换 curated 描述。
- **重写标注**：`【保留】`。

### `tools/__init__.py`（88 行）
- **职责**：工具公共入口。`delegate` 与 task 工具工厂用惰性 `__getattr__` 避免包级循环。
- **重写标注**：`【保留】`。

### 11.2 只读文件/搜索工具

### `tools/view.py`（71 行）
- **职责**：按行读取 UTF-8 文本文件（分页）。
- **对外 API**：`create_view_tool(root, *, access=None)`；`view(path, offset=0, limit=200)`。
- **设计原理**：`sandbox.resolve_validated` + `safe_read_text`；data 含 `path/start_line/end_line/truncated/total_lines`（供 lifecycle 分类）。
- **重写标注**：`【保留】`。

### `tools/ls.py`（42 行）
- **职责**：列出目录项（名 + 类型）。
- **重写标注**：`【保留】`。

### `tools/grep.py`（246 行）
- **职责**：固定字符串文本搜索。优先 ripgrep，fallback 纯 Python。
- **对外 API**：`create_grep_tool(root, *, access=None)`；`grep(pattern, path=".", include="*", case_sensitive=False, max_results=50)`。
- **重写标注**：`【保留】`。

### `tools/glob.py`（34 行）
- **职责**：glob 路径匹配。
- **重写标注**：`【保留】`。

### `tools/tree.py`（70 行）
- **职责**：目录树查看。
- **重写标注**：`【保留】`。

### `tools/read_multi.py`（101 行）
- **职责**：批量读多个文件（共享输出预算）。`target_builder=read_multi_target`（多路径权限）。
- **重写标注**：`【保留】`。

### 11.3 文件变更工具

### `tools/write.py`（73 行）
- **职责**：写文件。permission=WRITE_PATH target=path。
- **重写标注**：`【保留】`。

### `tools/edit.py`（71 行）
- **职责**：替换文本片段（默认唯一匹配）。permission=WRITE_PATH。
- **重写标注**：`【保留】`。

### `tools/delete.py`（58 行）
- **职责**：删除文件/目录（目录必须 recursive）。permission=DELETE_PATH。
- **重写标注**：`【保留】`。

### `tools/apply_patch.py`（372 行）—— 重点精读
- **职责**：多文件结构化 patch 工具。
- **对外 API**：`create_apply_patch_tool(root, *, access=None)`；`PatchHunk(old_lines, new_lines)`；`PatchOperation(action, path, move_to, add_lines, hunks)`；`PatchPlan(operations)`；`parse_patch(patch)`、`_apply_plan(sandbox, plan, *, dry_run)`。
- **核心流程**：
```
parse_patch：语法是自定义的 `*** Begin Patch` ... `*** End Patch`
  - `*** Add File: <path>` + 以 + 开头的内容行
  - `*** Update File: <path>` + 可选的 `*** Move to: <path>` + 以 @@ 开头的 hunk
    （hunk 行：+ 新 / - 旧 / 空格 上下文 / 空行）
  - `*** Delete File: <path>`
_apply_plan：先规划（pending_writes/pending_deletes），dry_run 时不落盘；
  每个 hunk 必须唯一匹配，否则报错
permission=WRITE_PATH，target_builder 从 patch 里提取所有涉及文件；allow_always=False, allow_auto=False
```
- **设计原理**：`*** Begin/End Patch` 是自定义语法（非标准 unified diff），但对模型是稳定契约。`_apply_plan` 支持 dry-run，是 `tools/review.py` 写前预览的核心。
- **重写标注**：`【保留】`（若重写沿用该语法；否则 `【必须改】` 换标准 diff 也行）。

### `tools/file_feedback.py`（39 行）
- **职责**：文件变更工具共享的 diff 与 no-op 反馈。`render_text_diff`、`format_change_content`。
- **重写标注**：`【保留】`。

### 11.4 执行工具

### `tools/shell.py`（102 行）
- **职责**：shell 命令执行（高风险）。permission=EXECUTE_SHELL target=command。
- **设计原理**：`ExecutionSandbox.run`（独立进程组、env 脱敏、超时/取消、输出截断）；env 覆盖拒绝敏感 key；超时时附加 agent guidance（建议 process_start）。
- **重写标注**：`【保留】`。

### `tools/python_exec.py`（94 行）
- **职责**：Python 代码执行。permission=EXECUTE_SHELL target=python -c <preview>；allow_always=False, allow_auto=False。
- **重写标注**：`【保留】`。

### `tools/processes.py`（229 行）
- **职责**：长期进程工具（process_start/status/logs/stop）。
- **重写标注**：`【简化】`。

### `tools/diagnostics.py`（82 行）
- **职责**：运行验证命令（默认 pytest）。permission=EXECUTE_SHELL。
- **重写标注**：`【保留】`。

### `tools/command_result.py`（49 行）
- **职责**：命令类工具共享结果格式化。`command_tool_result(name, result, *, data, nonzero_error, success_fallback)`。
- **重写标注**：`【保留】`。

### 11.5 网络工具

### `tools/fetch.py`（73 行）
- **职责**：HTTP GET，拒绝私网/本机地址。permission=NETWORK_REQUEST。
- **重写标注**：`【保留】`。

### `tools/web_search.py`（239 行）
- **职责**：网页搜索。默认 Parallel MCP（免费无 key），有 EXA_API_KEY 时回退 Exa。
- **核心流程**：`web_search` 按 provider 顺序尝试；调用 MCP JSON-RPC（直接 `urllib` POST）；`parse_mcp_search_response` 解析 JSON 或 SSE；`_redact_url` 避免 API key 写入 metadata。
- **设计原理**：参考 opencode 的 Exa MCP 约定（key 作查询参数）。
- **重写标注**：`【必须改】`（搜索 provider 是外部依赖，重写可替换为自己的搜索后端）。

### 11.6 git 工具

### `tools/git_status.py` / `git_diff.py` / `git_log.py`
- **职责**：查看 git 状态/diff/log。permission=GIT_OPERATION。
- **重写标注**：`【保留】`。

### 11.7 控制面 / 规划 / 会话工具

### `tools/think.py`（21 行）
- **职责**：无副作用推理工具。`think(thought)`。
- **重写标注**：`【保留】`。

### `tools/ask_user.py`（41 行）
- **职责**：向用户提问（返回 `requires_user_input=True`，loop 暂停）。
- **重写标注**：`【保留】`。

### `tools/delegate.py`（115 行）
- **职责**：delegate 工具。`create_delegate_tool(runner, *, parent_session_id, parent_task_hash)`；`role_allows_background`、`role_requires_worktree`。
- **重写标注**：`【简化】`。

### `tools/background.py`（94 行）
- **职责**：后台控制面工具（background_status / background_cancel）。
- **重写标注**：`【简化】`。

### `tools/task_boundary.py`（113 行）
- **职责**：task_boundary 工具（只收 decision + basis_message_id，拒收 hash）。
- **重写标注**：`【保留】`。

### `tools/task_create.py` / `task_update.py` / `task_revise.py` / `task_list.py` / `task_plan_support.py`
- **职责**：TaskPlan 工具族。`task_plan_support.py` 提供 `format_task_plan_snapshot` 与 `execute_task_plan_mutation`（RevisionConflict → 引导 task_list 重试）。
- **重写标注**：`【简化】`（TaskPlan 可选）。

### `tools/retrieve_archive.py`（202 行）
- **职责**：会话绑定检索 archive 原文。
- **核心流程**：`retrieve_archive(archive_id, query=None, max_chars=6000, full=False)`：query 模式返回匹配行窗口（±2 行）；full 返回原文；否则诊断模式（metadata + head/tail）。成功结果带 `archive_retrieval=True, compaction_protected_until_turn=current_turn()`，保护该 part 不被后续压缩吞掉。
- **重写标注**：`【保留】`。

### `tools/load_skill.py`（67 行）
- **职责**：加载已注册 skill 作为普通工具结果。写 `skill_selected` / `skill_loaded` 事件。
- **重写标注**：`【简化】`。

### `tools/hidden.py`（6 行）
- **职责**：`HIDDEN_TOOL_STATUS_NAMES = {"task_boundary"}`（不进 TUI 活动流）。
- **重写标注**：`【保留】`。

### 11.8 权限 / 结果 / 描述辅助

### `tools/permission_results.py`（99 行）
- **职责**：权限专用 ToolResult helper（denied / confirmation / prewrite review stale/failed）。
- **重写标注**：`【保留】`。

### `tools/path_permissions.py`（34 行）
- **职责**：`with_read_permission(tool, *, reason, target_builder=read_path_target)`；`read_multi_target`。
- **重写标注**：`【保留】`。

### `tools/descriptions.py`（70 行）
- **职责**：模型可见工具描述（curated TOOL_DESCRIPTIONS + `apply_agent_tool_description`）。
- **重写标注**：`【必须改】`（描述文案要重写，但机制保留）。

### `tools/review.py`（441 行）—— 重点精读
- **职责**：受信任的写前预览（prewrite review）。
- **对外 API**：`ReviewOperation`；`ReviewFile(path, operation, before_digest, after_digest, diff, added_lines, removed_lines, source_path, binary, snapshot)`；`ReviewSummary`；`PrewriteReview(tool_name, files, summary, error)`（`ok`、`to_payload()`、`is_current(root, *, access)`）；`supports_prewrite_review(tool_name)`；`build_prewrite_review(root, tool_call, *, access)`。
- **核心流程**：
```
build_prewrite_review：只支持 write/edit/apply_patch/delete
  write → _review_write（解析目标；计算 before/after）
  edit → _review_edit（old 唯一匹配）
  apply_patch → _review_apply_patch（parse_patch → dry-run 投影前后状态 → 每文件 ReviewFile）
  delete → _review_delete（递归列出将被删文件）
  is_current：对比 snapshot（path → digest）判断审查时文件是否已变化（过期）
```
- **设计原理**：用沙箱 dry-run 计算每个文件操作前后的 digest 与 unified diff，用户确认后若 snapshot 变化则拒绝（stale）。这是「直接文件修改」类工具的安全门。
- **重写标注**：`【保留】`。

---

## 12. 技能层（skills/ 全部）

### `skills/models.py`（78 行）
- **职责**：Skill 数据模型。`SkillSource`（PROJECT/GLOBAL × MARKDOWN/AGENT_SKILL）；`SkillDefinition(name, path, source, root, description, triggers)`；`LoadedSkill(skill, content, required_files)`；`SkillCatalog(skills, index_content)`（`resolved()`、`fingerprint`）。
- **重写标注**：`【保留】`。

### `skills/discovery.py`（213 行）
- **职责**：发现项目本地与机器全局 skill。
- **核心流程**：项目 `<root>/skills/*.md`（跳 INDEX.md）+ `<root>/.agents/skills/*/SKILL.md`；全局 `~/.agents/skills`、`~/.codex/skills`、`~/.firstcoder/skills` + `FIRSTCODER_SKILL_ROOTS`。解析 YAML frontmatter（name/description/triggers）。
- **重写标注**：`【简化】`。

### `skills/catalog.py`（94 行）
- **职责**：解析去重 + 渲染模型可见目录。`resolve_skill_catalog`（同名取最高优先级 source）；`render_skill_catalog`（固定预算 ≤8000 字符，描述逐条截断）。
- **重写标注**：`【简化】`。

### `skills/loader.py`（72 行）
- **职责**：加载 skill 文件（校验 path 不逃逸 root）；提取 required files。
- **重写标注**：`【简化】`。

### `skills/session.py`（40 行）
- **职责**：session 审计事件。`append_skill_selected`、`append_skill_loaded`。
- **重写标注**：`【简化】`。

### `skills/__init__.py`（12 行）
- **职责**：导出。
- **重写标注**：`【保留】`。

---

## 13. 输入与运行时（input/、runtime/ 全部）

### `input/attachments.py`（414 行）—— 重点精读
- **职责**：附件发现、暂存与 provider 准备。
- **对外 API**：`UserAttachment(kind, path, filename, media_type, size_bytes, source)`；`PreparedAttachment(kind, filename, media_type, size_bytes, relative_path, sha256, source, inline_text)`；`attach_path`；`extract_explicit_image_references(text)`；`resolve_explicit_image_references(text, *, workspace_root)`；`parse_path_candidates(text)`；`resolve_paste_attachments(paste_text=None, *, include_clipboard_image=True)`；`prepare_attachments_for_session(attachments, *, store_root, session_id)`；`load_image_base64(path)`；`format_attachment_chip`；`guess_media_type`、`is_image_media_type`、`is_text_like_media_type`。
- **核心流程**：`prepare_attachments_for_session` 把附件拷到 `<store_root>/attachments/<session_id>/`，文件名 `sha256[:16]-safe_name`；文本类小文件内联，大文件/图片只存路径引用。
- **重写标注**：`【保留】`（多模态输入）。

### `input/clipboard.py`（137 行）
- **职责**：OS 剪贴板图片读取（macOS/Linux/Windows）。
- **重写标注**：`【简化】`。

### `input/__init__.py`（19 行）
- **职责**：导出。
- **重写标注**：`【保留】`。

### `runtime/user_input.py`（97 行）—— 重点精读
- **职责**：结构化用户输入请求（ask_user 与权限确认共享）。
- **对外 API**：`UserInputOption(id, label, description)`；`UserInputRequest(id, kind(ask_user|permission_confirmation), question, options, payload)`；`user_input_request_from_tool_result(result, *, tool_call_id, tool_name)`。
- **核心流程**：从 ToolResult.data 的 `requires_user_input` 重建 UserInputRequest；`kind` 字段区分语义，防止模型把权限提示伪装成普通问题。
- **重写标注**：`【保留】`。

### `runtime/cancellation.py`（53 行）
- **职责**：协作取消原语。
- **对外 API**：`CancellationToken`（`cancel/is_cancelled/raise_if_cancelled`）；`AgentCancelledError`；`current_cancellation_token()`；`cancellation_context(token)`（thread-local 临时暴露）。
- **重写标注**：`【保留】`。

### `runtime/__init__.py`（27 行）
- **职责**：导出跨层原语。
- **重写标注**：`【保留】`。

---

## 14. 应用层（app/ TUI 全部）

### 📌 `app/factory.py`（426 行）—— 重点精读
- **职责**：TUI 组装工厂——唯一知道「如何把 provider + context_manager + tools + MCP + session services 拼成一个可运行 app」的地方。
- **对外 API**：`create_firstcoder_app(*, project_root, data_root, provider, session_id, resume_session, tools, config, app_config, mcp_manager_factory, model_spec, allow_user_input, runtime_capabilities) -> FirstCoderApp`。
- **核心流程**：
```
resolved_data_root = data_root or <project>/.firstcoder
app_config = load_config(project_root)
model_catalog = app_config.model_catalog()
selected_profile = _initial_model_profile(catalog, model_spec, state_store.load())
provider = create_provider_for_model(app_config, profile)
（可选 task_boundary_classifier_model → 独立 classifier provider）
store = JsonlSessionStore(resolved_data_root)
background_manager = BackgroundJobManager()
process_manager = ProcessManager(log_root=resolved_data_root/processes)
resolved_tools = create_builtin_registry(project, mutation+execution+network, access)
mcp_manager = (mcp_manager_factory or McpManager)(load_mcp_configs(app_config))
mcp_manager.connect_all_in_background()
tool_provider = McpToolProvider(resolved_tools, mcp_manager, include_mcp)
session = bootstrap.resume(session_id) or bootstrap.from_project(session_id)
compact_summarizer = ProviderLlmCompactSummarizer(provider)
context_manager = ContextWindowManager(store, l4_service=LlmCompactService(store, summarizer))
各 service（Resume/New/Fork/Share）+ 各 CommandHandler（Help/Mcp/Model/Session/Context/Permission/Skill）
chat_runner = AgentChatRunner(current_session, provider, classifier_provider, tools, tools_provider,
    context_manager, limits, use_streaming, request_options, context_window, background_manager,
    runtime_capabilities)
command_handler = CompositeCommandHandler([...])
return FirstCoderApp(...)
```
- **设计原理**：把「运行时装配」集中在 factory，UI widget 不直接依赖 provider/agent 细节。`McpToolProvider` 把稳定 base 工具集与 MCP 目录合并。
- **重写标注**：`【保留】`。

### 📌 `app/runtime.py`（368 行）—— 重点精读
- **职责**：TUI 运行期 session 状态与聊天入口（当前 session 可替换、普通输入调用 AgentLoop）。
- **对外 API**：`CurrentSessionState(session)`（代理 session_id/runtime_state/current_turn/rebuild_view/mode/set_permission_mode/set_session）；`AgentChatRunner`：
  - `arun_user_turn(content, *, attachments=None) -> ChatResponse`、`aresume_with_user_input(request_id, answer)`、`run_user_turn`/`resume_with_user_input`（同步包装）。
  - `set_model`、`add_guidance`/`drain_guidance`、`cancel_current_turn`、`sync_pending_input_from_current_session`、`context_budget(view)`。
- **核心流程**：
```
arun_user_turn：
  before_count = len(view.messages)；token = _begin_cancellable_turn()
  loop = _create_loop(token, streaming)   # AgentLoop(session, provider, ..., context_manager,
                                          #  guidance_provider=drain_guidance, ...)
  result = anyio.to_thread.run_sync(_run_coroutine_in_thread,
            loop.run_user_turn(content, streaming=self.use_streaming))
  return _finish_agent_result(before_count, loop, result)
_finish_agent_result：last_pending_input = result.pending_input；
  _remember_pending_permission_loop（仅当 pending_permission_execution 非空）；
  _refresh_turn_output（读 view[before_count:] 压成 TUI 可读短行）
```
- **设计原理**：UI 不需要知道 AgentLoop 编排细节；`guidance_provider` 让运行中的 turn 可排队注入额外指引；权限恢复复用同一个 AgentLoop（预算/状态延续），并 rebind stream/tool handler。
- **重写标注**：`【保留】`。

### 📌 `app/tui.py`（863 行）—— 重点精读
- **职责**：FirstCoder 最小 Textual TUI 外壳。
- **对外 API**：`FirstCoderApp(FirstCoderViewMixin, App)`：`command_handler, chat_runner, current_session, config, on_shutdown`。CSS_PATH="tui.tcss"；BINDINGS ctrl+c。核心方法：`_submit_composer`、`_submit_chat_text`、`_run_chat_turn`、`_resume_permission_turn`、`_write_chat_response`、`_handle_command_action`、`_open_picker`、`_replay_current_session`、`_interrupt_chat_turn`。
- **核心流程**：
```
_submit_composer：
  读输入；空 → return；数字且 picker 打开 → _picker_select_number
  写用户行；以 / 开头 → command_handler.handle(text)（特殊处理 /compact）
  否则 _staged_attachments.clear() + _submit_chat_text(text, attachments)
_submit_chat_text：
  chat_runner 为空 → error
  若 _chat_busy → chat_runner.add_guidance(text)（排队），return
  若 last_pending_input.kind == permission_confirmation →
    先尝试 review_command_from_text（"review all/path/clear"）→ 否则 permission_choice_for_text
    → _resume_permission_turn(pending.id, choice, token)
  否则 _begin_active_chat_turn + run_worker(_run_chat_turn(text, token))
_run_chat_turn：
  _install_stream_event_handler(token) + _install_tool_event_handler(token)
  response = await chat_runner.arun_user_turn(text, attachments)（或 aresume_with_user_input）
  异常 → 写 error 行；finally 恢复 handlers + _finish_chat_turn(token)
  _write_chat_response(response)：drain stream deltas；写 markdown 或 display lines；_write_pending_input
```
- **设计原理**：Textual widget 不直接依赖 provider/agent 细节，只持有 `command_handler`、`chat_runner`、`current_session` 三个注入。流式渲染用 timer 批量 flush markdown；工具事件用 `_call_ui_thread` 安全跨线程写 UI。
- **重写标注**：`【保留】`（若重写选 Textual 可照搬；换前端则仅保留状态模型思想）。

### `app/tui_view.py`（789 行）
- **职责**：渲染、活动动画与流式 helper（`FirstCoderViewMixin`）。
- **核心流程**：`_topbar_text`、`_write_line`、`_write_markdown_message`、`_install_stream_event_handler`（reasoning_delta/text_delta 排队）、`_install_tool_event_handler`（写工具状态行）、`_enqueue_stream_delta`/`_drain_stream_deltas`/`_append_stream_text`（markdown 分块更新）、`_finalize_stream_widget`（流结束才允许选中复制）。
- **重写标注**：`【简化】`（纯渲染细节）。

### `app/tui_state.py`（90 行）
- **职责**：TUI 状态模型。`TuiEntryKind`；`TuiTranscriptEntry(id, kind, body, label, status, widget)`；`TuiToolActivity`；`TuiTaskPlanPanelState`；`TuiTranscript`（`add`、`record_tool_activity`）。
- **重写标注**：`【保留】`。

### `app/tui_widgets.py`（156 行）
- **职责**：Textual 自定义 widget（FirstCoderMarkdown 选择门控、ComposerTextArea Enter 提交/Shift+Enter 换行/粘贴图片、FirstCoderScreen 尺寸通知）。
- **重写标注**：`【简化】`。

### `app/router.py`（24 行）
- **职责**：多个 slash command handler 的组合入口。`CompositeCommandHandler.handle(text)`：第一个 `result.handled` 即返回；否则未知命令报错。
- **重写标注**：`【保留】`。

### `app/ports.py`（36 行）
- **职责**：app 边界协议（CommandHandlerLike / ChatRunnerLike / CurrentSessionLike / ContextManagerLike）。
- **重写标注**：`【保留】`。

### `app/commands.py`（151 行）
- **职责**：`/context`、`/compact status`、`/compact` 处理。`ContextCommandHandler(session, budget_provider, context_manager, inspector)`。
- **重写标注**：`【保留】`。

### `app/session_commands.py`（243 行）
- **职责**：`/new /fork /sessions /session /resume /share /rename`。
- **重写标注**：`【保留】`。

### `app/model_commands.py`（86 行）与 `app/model_state.py`（105 行）
- **职责**：`/model` 切换 + 项目级模型选择偏好持久化（`ModelStateStore` 原子写 JSON）。
- **重写标注**：`【保留】`。

### `app/permission_commands.py`（46 行）与 `app/permission_view.py`（93 行）
- **职责**：`/mode` 权限切换；权限提示渲染与回答解析。
- **重写标注**：`【保留】`。

### `app/help_commands.py`（44 行）
- **职责**：`/help`。
- **重写标注**：`【保留】`。

### `app/mcp_commands.py`（61 行）
- **职责**：`/mcp list|doctor|reconnect`。
- **重写标注**：`【简化】`。

### `app/skill_commands.py`（148 行）
- **职责**：`/skills /skill /skill-use` 与精确 `/<skill-name>`。
- **重写标注**：`【简化】`。

### `app/activity_view.py`（219 行）
- **职责**：活动行、工具事件与 task-plan 面板渲染 helper。
- **重写标注**：`【简化】`。

### `app/review_view.py`（123 行）
- **职责**：写前预览的 rich 渲染与输入解析。
- **重写标注**：`【保留】`。

### `app/transcript_view.py`（79 行）
- **职责**：transcript 条目分类与 CSS helper。
- **重写标注**：`【简化】`。

### `app/topbar_view.py`（46 行）、`app/yuren_topbar_themes.py`（58 行）、`app/welcome.py`（97 行）、`app/picker.py`（87 行）、`app/picker_adapters.py`（57 行）、`app/tui.tcss`（181 行）
- **职责**：顶部栏渲染、Yuren 彩蛋主题、欢迎动画、picker 状态/渲染、CSS。
- **重写标注**：`【简化】`（彩蛋/welcome 可直接砍掉）。

### `app/__init__.py`（6 行）
- **职责**：导出。
- **重写标注**：`【保留】`。

---

## 15. 工具类（utils/ 全部）

### `utils/sandbox_access.py`（20 行）
- **职责**：`SandboxAccessMode`（PROJECT/UNRESTRICTED）；`SandboxAccess(mode)`，`unrestricted` property。
- **重写标注**：`【保留】`。

### `utils/sandbox.py`（62 行）
- **职责**：路径沙箱。`PathSandbox(root, access)`：`resolve(path)`（越界抛 ValueError）、`resolve_validated(path, *, expect)`、`relative(path)`。
- **重写标注**：`【保留】`。

### `utils/execution_sandbox.py`（101 行）
- **职责**：子进程沙箱。`ExecutionSandbox(root, access)`：`resolve_cwd`、`build_env(extra_env)`（剔除敏感 key：KEY/TOKEN/SECRET/PASSWORD/COOKIE）、`prepare_env_overrides(extra_env)`、`run(...)`（透传取消令牌）。
- **重写标注**：`【保留】`。

### `utils/subprocess.py`（221 行）
- **职责**：子进程执行通用工具。`CommandResult`；`run_command(command, *, cwd, timeout_seconds, max_output_chars, shell, env, cancellation_token)`；`process_group_kwargs()`、`terminate_process_group(process)`。
- **核心流程**：独立进程组启动；`communicate` 循环支持取消；超时/中断 → `_terminate_process_group`（Windows taskkill / POSIX killpg+SIGKILL）；`truncate_head_tail` 截断输出。
- **重写标注**：`【保留】`。

### `utils/git.py`（27 行）
- **职责**：`run_git(sandbox, args)`（脱敏 env 运行 git）。
- **重写标注**：`【保留】`。

### `utils/introspection.py`（86 行）
- **职责**：`tool_from_function(func)`、`function_to_parameters(func)`（签名 → JSON Schema）。
- **重写标注**：`【保留】`。

### `utils/json_utils.py`（39 行）
- **职责**：`dumps_json`、`loads_json`（严格）、`loads_json_object`（失败保留原字符串）。
- **重写标注**：`【保留】`。

### `utils/schema.py`（27 行）
- **职责**：`property_schema(type, **extra)`、`object_schema(properties, required)`。
- **重写标注**：`【保留】`。

### `utils/text.py`（82 行）
- **职责**：`truncate`、`truncate_head_tail`、`safe_read_text`、`optional_str`、`display_value`、`model_label`、`ellipsis_truncate`。
- **重写标注**：`【保留】`。

### `utils/__init__.py`（1 行）
- **职责**：docstring。
- **重写标注**：`【保留】`。

---

## 16. 横切关注点汇总

### 16.1 消息事实模型 vs provider 消息的分离

- **现状**：
  - 事实模型：`context/models.py` 的 `AgentMessage(id, session_id, role, parts, created_at, metadata)` 与 `MessagePart(id, message_id, kind, content, metadata)`。这是 JSONL 里持久化的账本，`kind` 覆盖 `text/tool_call/tool_result/checkpoint_summary/compaction_event_ref/archive_placeholder`。
  - provider 消息：`providers/types.py` 的 `ChatMessage(role, content, content_parts, name, tool_call_id, tool_calls)`。`ContextBuilder.build_provider_messages` 每轮把 `SessionView` 投影成 `ChatMessage[]`。
  - 投影规则（`context/context_builder.py`）：system_meta 不投影；tool part 只投影 `tool_result/archive_placeholder`；assistant 合并 text + tool_calls；user 加 `[context: basis_message_id=...]` 锚点、可选图片 content_parts。
  - 写入侧：`context/writer.py` 的 `tool_call_to_part` / `tool_result_to_part` 把 provider 响应转回事实 part（metadata 存 `tool_call_id/tool_name/arguments/ok/data/error`）。
- **为什么这样设计**：FirstCoder 把「长期可恢复事实」与「每次请求的线格式」解耦。压缩/checkpoint 只改投影结果不删事实；resume 时完整重放 JSONL 得到全部事实，再重新投影。若两者合一，压缩就会破坏可恢复性。
- **对我们重写的启示**：这是必须保留的顶层架构。重写时**先定 `AgentMessage/MessagePart/SessionView` 模型，再写 ContextBuilder 投影**，然后才有 provider 适配层。不要用 provider 消息格式直接当持久化格式。

### 16.2 Session 持久化与恢复（JSONL、索引、fork、bootstrap、checkpoint、archive）

- **现状**：
  - JSONL：`context/store.py` `JsonlSessionStore`，`append_event` 写 `<root>/sessions/<id>.jsonl`，`rebuild_session_view` 逐事件重放。事件类型：`session_created/session_metadata_updated/user_message/assistant_message/tool_result/background_notification/checkpoint_created/compaction_completed/compaction_skipped/llm_compaction_completed/message_part_metadata_updated/task_plan_updated/task_boundary_observed/provider_projection_consumed/agent_turn_telemetry/skill_selected/skill_loaded`。
  - 索引：`session/index.py` `SessionIndex`，`session_index.json` 缓存列表摘要；store 每次 append 后同步 `update_event`。
  - resume：`session/resume.py` `ResumeService` + `validate_session_schema`（schema 版本硬边界）。`AgentSession.resume` 重放 runtime state + 重建 known_message_ids/tool_result 幂等索引 + restore pending permission。
  - fork：`session/fork.py` 事件级浅拷贝 + archive 目录拷贝。
  - bootstrap：`session/bootstrap.py` 统一 new/resume/fork 的 AgentSession 装配。
  - checkpoint：`context/checkpoint.py`，只记边界不删历史；`ContextBuilder` 投影时插入 summary。
  - archive：`context/archive.py` 内容寻址存储压缩结果原文，`retrieve_archive` 工具可找回。
- **为什么这样设计**：append-only + 重放让「任何时刻的会话状态」都可确定性重建；checkpoint 是投影层优化不是存储层删除。schema 版本硬边界避免旧/未来格式破坏重放。
- **对我们重写的启示**：JSONL + 事件重放是核心，照搬。若规模顾虑，可以保留「事件日志」抽象、实现层面换成 SQLite/duckdb，但 `rebuild_session_view` 语义必须等价。

### 16.3 Context 投影管线（budget → lifecycle → compaction → provider 消息）

- **现状**：每次 provider 请求前：`loop._prepare_main_provider_request` → `build_context_budget`（`context/token_budget.py`）→ `context_manager.compact_if_needed`（`context/manager.py`）→ `CompactionPipeline`（L1 trim 旧任务对话 / L2 route 压缩 DERIVED / L3 archive 占位）→ 必要时 L4 LLM 摘要（`llm_compact.py` + `provider_summarizer.py`）→ `ContextBuilder.build_provider_messages`。`tool_lifecycle.py` 提供 L2/L3 的决策依据。
- **为什么这样设计**：把「是否压缩/压缩到哪层」做成策略（manager），「怎么压」做成执行（pipeline + content/ 路由压缩器），「压成什么」做成产物（checkpoint/archive）。budget 用高低水位驱动，AUTO/PROMPT_TOO_LONG/TASK_HASH_CHANGED/MANUAL 四种触发共享同一管线。
- **对我们重写的启示**：压缩管线是 FirstCoder 最大的资产。重写时：L1（旧任务 trim）与 L3（archive 占位）语义直接照搬；L2 内容路由压缩器可简化（只留 plain_text fallback + json）；L4 LLM 摘要可后置。token 估算换成真实 tokenizer 时，`ContextBudget`/`estimate_tokens` 接口不变。

### 16.4 工具执行、证据与结算（tool_flow / tool_execution / tool_settlement / execution_evidence）

- **现状**：
  - `tool_flow.py`：provider 响应 ↔ 事实 part 的转换。
  - `tool_execution.py`：先权限、后执行、再结算；权限 ASK 暂停；后台控制字段剥离；只读并行批。
  - `tool_settlement.py`：skipped/interrupted/repair——保证 tool_call/tool_result 配对闭合。
  - `execution_evidence.py`：benchmark 专用，记录修改/验证/后台证据，阻止过早收尾。
- **为什么这样设计**：工具执行有副作用，必须「权限在前、事实在后」。中断/暂停/跳过都不能留下悬空 tool_call；`_tool_result_message_ids` 保证同一 tool_call 幂等落一条结果。
- **对我们重写的启示**：工具执行的状态机（权限预检 → 执行 → 结算）是必须保留的核心。benchmark 证据门禁（execution_evidence/stagnation）可砍。

### 16.5 错误处理：provider 重试、停滞检测、任务边界

- **现状**：
  - Provider 错误分类：`providers/errors.py` `ProviderErrorKind` + `retryable`/`requires_compaction`。
  - 重试：`agent/provider_retry.py` 指数退避；`loop._complete_once_with_recovery` 处理 retryable 与 prompt-too-long 压缩恢复。
  - 停滞检测：`agent/stagnation.py`（benchmark 专用，相同失败 3 次后阻断第 4 次）。
  - 任务边界：`agent/task_boundary_classifier.py` 隐藏 LLM 分类 + `context/task_boundary.py` 稳定 hash + 稳定计数。
- **为什么这样设计**：错误分层——provider 错误归类在 providers 层，恢复策略在 loop 层，停滞检测在 benchmark 层，任务边界在 context 层。每层只处理自己该处理的事。
- **对我们重写的启示**：错误分类 + 重试 + prompt-too-long 恢复是通用能力，照搬。任务边界（task hash + 稳定计数 + 压缩联动）是 FirstCoder 特色，值得保留但可简化。停滞检测是 benchmark 特有。

### 16.6 权限与安全（grants / policy / manager）

- **现状**：`PermissionManager`（组合 grants + policy）→ `PermissionAwareToolRegistry.preflight` → 工具声明 `ToolPermissionSpec` 驱动 `PermissionRequest` → `Policy.decide`（路径/环境变量/git/shell/网络/MCP 分类决策）→ ASK 暂停 → `resolve_confirmation`（deny / reject_with_feedback / allow_once / allow_always_same_scope）。
- **为什么这样设计**：纯函数策略（好测）+ 显式 grant 覆盖（deny 优先）+ ASK 暂停（不自动执行）。工具声明与执行分离。
- **对我们重写的启示**：权限系统是安全底线，照搬。`path_access`/`env_secrets` 等策略细节可按需调整；AGGRESSIVE/BYPASS 模式与 benchmark 联动可简化。

### 16.7 可观测性（telemetry、events、运行时事件）

- **现状**：`agent/telemetry.py` 结构化计数写 `agent_turn_telemetry` 事件；`context/inspector.py` 只读调试报告（`/context`）；TUI 用 `ToolExecutionEvent`/`ChatStreamEvent` 实时渲染；provider 流式事件 `reasoning_delta/text_delta/tool_call_*`。
- **为什么这样设计**：遥测只存计数不存敏感数据；事件既持久化又驱动 UI，一套数据两用。
- **对我们重写的启示**：turn telemetry 结构值得保留（诊断/审计）；TUI 事件模型（provider stream 与工具事件分离）是干净设计。

### 16.8 TUI 状态管理与渲染

- **现状**：`TuiTranscript` 增量条目模型 + `FirstCoderViewMixin` 渲染/动画 + 流式 markdown 分块 flush + 工具事件跨线程 `call_from_thread`。command 层用 `CompositeCommandHandler` 组合各 handler，返回 `CommandResult(handled, output, action)`；action 驱动 UI（开 picker、回放会话、切换模型）。
- **为什么这样设计**：widget 只做显示，命令/会话/上下文逻辑全在 handler；`action` 解耦「命令输出」与「UI 行为」。
- **对我们重写的启示**：若重写继续用 Textual，`FirstCoderViewMixin` + handler 组合可照搬；否则保留「CommandResult + action」的薄命令层即可。

### 16.9 多代理 / 后台 / 子代理（subagent / background / processes / worktree）

- **现状**：`BackgroundJobManager`（ThreadPoolExecutor + 占位结果 + notification）；`SubagentRunner`（角色裁剪工具、独立子会话、防递归）；`WorktreeManager`（git worktree 隔离后台 coder）；`ProcessManager`（长期服务进程组 + readiness）。
- **为什么这样设计**：后台执行与「tool_call 必须闭合」的协议约束对齐——原始 id 立即有占位结果，真结果以独立 notification 注入。子代理用全新 session + 角色权限 + worktree 隔离保证安全。
- **对我们重写的启示**：后台任务（占位 + notification）值得保留；子代理与 worktree 隔离是高级能力可延后；ProcessManager 是 Terminal-Bench 特需可后置。

---

## 17. 翻译式重写评估表

### 17.1 总表

| 模块 | FirstCoder 规模 | 重写标注 | 保留的核心语义 | 可简化的外围 | 必须改的点 |
|---|---|---|---|---|---|
| `cli.py` + 入口 | ~600 | 【保留】 | 三模式分发、benchmark 分支、REPL | 权限文本别名 | 去掉 yurenapi 默认配置 |
| `config/` | ~500 | 【保留】 | AppConfig 优先级、ModelCatalog 校验 | 厂商预设列表 | default_model 模板 |
| `context/models.py` | ~110 | 【保留】 | AgentMessage/MessagePart/SessionView | — | — |
| `context/events.py` `store.py` `writer.py` | ~640 | 【保留】 | append-only 事件、重放、turn 元数据补齐 | — | 事件类型可按需精简 |
| `context/context_builder.py` | ~290 | 【保留】 | 投影规则、tool 序列校验、basis_message_id | — | — |
| `context/token_budget.py` | ~110 | 【保留】 | 预算/水位 | — | 可换真实 tokenizer |
| `context/compaction.py` | ~785 | 【保留】 | L1 trim / L3 archive 语义、lifecycle 驱动 | L2 内容压缩细节 | — |
| `context/manager.py` | ~620 | 【保留】 | L1-L4 编排、熔断、fallback | — | — |
| `context/checkpoint.py` `archive.py` | ~400 | 【保留】 | 边界摘要 + 内容寻址存储 | — | — |
| `context/llm_compact.py` + summarizer | ~580 | 【保留】 | L4 摘要 + 边界校验 | — | prompt/格式可改 |
| `context/content/*` | ~1,500 | 【简化】 | 路由框架 + plain_text/json fallback | 各语言专用压缩器 | — |
| `context/task_boundary.py` | ~305 | 【保留】 | 稳定 hash + 稳定计数 | — | — |
| `context/runtime_state/replay/inspector/triggers/system_prompt/identity/metadata/versions/fallback/retry_policy/tool_sequence` | ~900 | 【保留】 | 运行期状态、熔断、指纹、system prompt 缓存 | — | — |
| `agent/loop.py` | ~1,630 | 【保留】 | 单轮事务、权限暂停、压缩联动、tool 过滤 | benchmark gate 分支 | — |
| `agent/session.py` | ~670 | 【保留】 | 运行时容器、幂等 tool_result、pending 恢复 | — | — |
| `agent/tool_execution.py` | ~620 | 【保留】 | 权限→执行→结算状态机、后台剥离 | 并行只读批 | — |
| `agent/tool_settlement.py` | ~56 | 【保留】 | 配对闭合 | — | — |
| `agent/background.py` | ~450 | 【保留】 | 占位结果 + notification 协议 | — | — |
| `agent/execution_evidence.py` | ~510 | 【必须改】 | 修改/验证/后台证据思路 | — | Terminal-Bench 特有，整块可砍 |
| `agent/stagnation.py` | ~180 | 【简化】 | 相同失败阻断思路 | — | benchmark 特有 |
| `agent/telemetry.py` | ~160 | 【保留】 | 结构化计数 | — | — |
| `agent/task_boundary_classifier.py` | ~130 | 【简化】 | 隐藏分类思路 | prompt/降级 | — |
| `agent/subagent.py` + `worktree.py` + `delegate.py` | ~900 | 【简化】 | 角色裁剪子代理 | worktree 隔离 | — |
| `agent/processes.py` | ~200 | 【简化】 | 进程组 + readiness | — | Terminal-Bench 特需 |
| `agent/loop_limits/provider_retry/runtime_capabilities/prompt_inputs/ports/user_input` | ~500 | 【保留】 | 预算、退避、能力开关 | benchmark 分支 | — |
| `providers/*` | ~1,600 | 【保留】 | ChatProvider 抽象、错误分类、streaming 桥 | Anthropic 实现 | — |
| `permissions/*` | ~900 | 【保留】 | 纯策略 + grant + ASK | 模式联动 | — |
| `planning/*` | ~800 | 【简化】 | reducer + 版本快照 | 文件锁 | — |
| `session/*` | ~1,000 | 【保留】 | catalog/resume/fork/schema 边界 | share/transcript/redaction | — |
| `skills/*` | ~500 | 【简化】 | 发现/加载/审计事件 | 多 root | — |
| `mcp/*` | ~1,000 | 【简化】 | manager 桥接 + adapter | search | — |
| `input/*` | ~570 | 【简化】 | 附件 staging | 剪贴板 | — |
| `runtime/*` | ~180 | 【保留】 | 取消令牌 + UserInputRequest | — | — |
| `utils/*` | ~760 | 【保留】 | 沙箱/子进程/文本 | — | — |
| `app/factory.py` + `app/runtime.py` | ~800 | 【保留】 | 装配根 + AgentChatRunner | — | — |
| `app/tui*.py` + views | ~3,000 | 【简化】 | TuiTranscript 状态 + handler 组合 | 动画/welcome/彩蛋 | — |

### 17.2 建议的重写优先级

**第一批（核心 spine，必须最先写，顺序即依赖方向）**：
1. `runtime/`（cancellation + UserInputRequest）——全仓最底层。
2. `utils/`（sandbox/subprocess/text/json/schema）。
3. `config/`（AppConfig + ModelCatalog）。
4. `providers/`（types/errors/base/streaming/openai_compatible/factory）。
5. `context/` 的骨架：models/events/identity/versions/metadata/tool_sequence/store/writer/token_budget/context_builder。
6. `permissions/`（types/policy/grants/manager）。
7. `tools/` 骨架：types/registry/introspection + 只读工具（view/ls/grep/glob/tree/read_multi）+ 文件工具（write/edit/delete/apply_patch）+ permission_registry + review。
8. `agent/`：session.py → tool_flow/tool_settlement → tool_execution → loop.py → loop_limits/provider_retry/telemetry/ports/user_input。
9. `session/`：bootstrap/catalog/resume。
10. `app/factory.py` + `app/runtime.py` + 最简 TUI（tui.py/commands/router/ports）。
11. `cli.py` 单消息 + REPL 模式。

**第二批（核心能力补全）**：
12. `context/` 压缩管线：checkpoint/archive/compaction/lifecycle/triggers/manager/runtime_state/runtime_replay（自动压缩与 prompt-too-long 恢复）。
13. `context/content/` 的 plain_text + json fallback。
14. `tools/` 执行工具（shell/python_exec/command_result/diagnostics）。
15. `agent/background.py`（若需要后台）+ `agent/task_boundary_classifier` + `context/task_boundary`。
16. `context/system_prompt.py` + prompts。

**第三批（可选能力，可延后/可砍）**：
17. `context/llm_compact.py`（L4）+ provider_summarizer + fallback/retry_policy（需要时再写）。
18. `context/content/*` 专用压缩器（diff/build/code/html/search）。
19. `planning/` 与 task 工具族。
20. `skills/`。
21. `mcp/`。
22. `session/` 的 fork/share/transcript/redaction。
23. `input/` 附件与剪贴板。
24. `app/` 渲染细节（picker/welcome/topbar/activity/review_view）。
25. `agent/subagent + worktree + delegate`、`agent/processes`。

**可砍（重写为通用 agent 时）**：
- `agent/execution_evidence.py`、`agent/stagnation.py`、`agent/runtime_capabilities.benchmark`、`cli.py` 的 benchmark 分支——Terminal-Bench 特有。
- `app/yuren_topbar_themes.py`、`app/welcome.py`——品牌彩蛋。

---

## 附录 A：文件覆盖清单

> 每个文件均映射到文档章节。括号内为章节号。标 📌 为重点精读文件。

### 根目录
| 文件 | 章节 |
|---|---|
| `__init__.py` | 2 |
| `__main__.py` | 2 |
| `cli.py` 📌 | 2 |

### agent/（21）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 5 |
| `background.py` 📌 | 5 |
| `execution_evidence.py` 📌 | 5 |
| `loop.py` 📌 | 5 |
| `loop_limits.py` | 5 |
| `ports.py` | 5 |
| `processes.py` | 5 |
| `prompt_inputs.py` | 5 |
| `provider_retry.py` | 5 |
| `runtime_capabilities.py` | 5 |
| `session.py` 📌 | 5 |
| `stagnation.py` 📌 | 5 |
| `subagent.py` 📌 | 5 |
| `task_boundary_classifier.py` 📌 | 5 |
| `task_plan_policy.py` | 5 |
| `telemetry.py` 📌 | 5 |
| `tool_execution.py` 📌 | 5 |
| `tool_flow.py` | 5 |
| `tool_settlement.py` 📌 | 5 |
| `user_input.py` | 5 |
| `worktree.py` | 5 |

### app/（26 + tui.tcss）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 14 |
| `activity_view.py` | 14 |
| `commands.py` | 14 |
| `factory.py` 📌 | 14 |
| `help_commands.py` | 14 |
| `mcp_commands.py` | 14 |
| `model_commands.py` | 14 |
| `model_state.py` | 14 |
| `permission_commands.py` | 14 |
| `permission_view.py` | 14 |
| `picker.py` | 14 |
| `picker_adapters.py` | 14 |
| `ports.py` | 14 |
| `review_view.py` | 14 |
| `router.py` | 14 |
| `runtime.py` 📌 | 14 |
| `session_commands.py` | 14 |
| `skill_commands.py` | 14 |
| `topbar_view.py` | 14 |
| `transcript_view.py` | 14 |
| `tui.py` 📌 | 14 |
| `tui_state.py` | 14 |
| `tui_view.py` | 14 |
| `tui_widgets.py` | 14 |
| `tui.tcss` | 14 |
| `welcome.py` | 14 |
| `yuren_topbar_themes.py` | 14 |

### config/（3）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 3 |
| `models.py` 📌 | 3 |
| `settings.py` 📌 | 3 |

### context/（27）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 9.1 |
| `archive.py` 📌 | 9.6 |
| `budget_defaults.py` | 9.2 |
| `checkpoint.py` 📌 | 9.6 |
| `compaction.py` 📌 | 9.5 |
| `context_builder.py` 📌 | 9.3 |
| `events.py` | 9.9 |
| `fallback.py` | 9.7 |
| `identity.py` | 9.9 |
| `inspector.py` | 9.9 |
| `llm_compact.py` 📌 | 9.7 |
| `manager.py` 📌 | 9.8 |
| `metadata.py` | 9.9 |
| `models.py` 📌 | 4 |
| `provider_summarizer.py` | 9.7 |
| `retry_policy.py` | 9.7 |
| `runtime_replay.py` | 9.8 |
| `runtime_state.py` 📌 | 9.8 |
| `store.py` 📌 | 9.9 |
| `system_prompt.py` | 9.9 |
| `task_boundary.py` 📌 | 9.9 |
| `token_budget.py` 📌 | 9.2 |
| `tool_lifecycle.py` 📌 | 9.4 |
| `tool_sequence.py` | 9.3 |
| `triggers.py` | 9.8 |
| `versions.py` | 9.9 |
| `writer.py` 📌 | 9.9 |

### context/content/（10）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 9.10 |
| `build.py` | 9.10 |
| `code.py` | 9.10 |
| `compressors.py` | 9.10 |
| `detector.py` | 9.10 |
| `diff.py` | 9.10 |
| `html.py` | 9.10 |
| `json.py` | 9.10 |
| `router.py` 📌 | 9.10 |
| `search.py` | 9.10 |

### context/prompts/（2）
| 文件 | 章节 |
|---|---|
| `agent_instructions.md` | 9.10 |
| `benchmark_agent_instructions.md` | 9.10 |

### input/（3）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 13 |
| `attachments.py` 📌 | 13 |
| `clipboard.py` | 13 |

### mcp/（8）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 10 |
| `adapter.py` | 10 |
| `config.py` | 10 |
| `config_store.py` | 10 |
| `manager.py` 📌 | 10 |
| `models.py` | 10 |
| `search.py` | 10 |
| `transport.py` | 10 |

### permissions/（5）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 7 |
| `grants.py` | 7 |
| `manager.py` 📌 | 7 |
| `policy.py` 📌 | 7 |
| `types.py` | 7 |

### planning/（6）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 8 |
| `models.py` | 8 |
| `projection.py` | 8 |
| `reducer.py` | 8 |
| `service.py` | 8 |
| `validation.py` | 8 |

### providers/（10）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 6 |
| `anthropic_provider.py` 📌 | 6 |
| `base.py` 📌 | 6 |
| `errors.py` | 6 |
| `factory.py` | 6 |
| `openai_compatible.py` 📌 | 6 |
| `presets.py` | 6 |
| `streaming.py` 📌 | 6 |
| `tool_adapters.py` | 6 |
| `types.py` 📌 | 6 |

### runtime/（3）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 13 |
| `cancellation.py` | 13 |
| `user_input.py` 📌 | 13 |

### session/（12）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 4 |
| `bootstrap.py` | 4 |
| `catalog.py` | 4 |
| `errors.py` | 4 |
| `fork.py` | 4 |
| `index.py` 📌 | 4 |
| `models.py` | 4 |
| `new.py` | 4 |
| `redaction.py` | 4 |
| `resume.py` | 4 |
| `share.py` | 4 |
| `transcript.py` | 4 |

### skills/（6）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 12 |
| `catalog.py` | 12 |
| `discovery.py` | 12 |
| `loader.py` | 12 |
| `models.py` | 12 |
| `session.py` | 12 |

### tools/（44）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 11.1 |
| `apply_patch.py` 📌 | 11.3 |
| `ask_user.py` | 11.7 |
| `background.py` | 11.7 |
| `builtin.py` | 11.1 |
| `command_result.py` | 11.4 |
| `delegate.py` | 11.7 |
| `delete.py` | 11.3 |
| `descriptions.py` | 11.8 |
| `diagnostics.py` | 11.4 |
| `edit.py` | 11.3 |
| `fetch.py` | 11.5 |
| `file_feedback.py` | 11.3 |
| `git_diff.py` | 11.6 |
| `git_log.py` | 11.6 |
| `git_status.py` | 11.6 |
| `glob.py` | 11.2 |
| `grep.py` | 11.2 |
| `hidden.py` | 11.7 |
| `load_skill.py` | 11.7 |
| `ls.py` | 11.2 |
| `path_permissions.py` | 11.8 |
| `permission_registry.py` 📌 | 11.1 |
| `permission_results.py` | 11.8 |
| `processes.py` | 11.4 |
| `python_exec.py` | 11.4 |
| `read_multi.py` | 11.2 |
| `registry.py` 📌 | 11.1 |
| `retrieve_archive.py` | 11.7 |
| `review.py` 📌 | 11.8 |
| `session_registry.py` | 11.1 |
| `shell.py` | 11.4 |
| `task_boundary.py` | 11.7 |
| `task_create.py` | 11.7 |
| `task_list.py` | 11.7 |
| `task_plan_support.py` | 11.7 |
| `task_revise.py` | 11.7 |
| `task_update.py` | 11.7 |
| `think.py` | 11.7 |
| `tree.py` | 11.2 |
| `types.py` 📌 | 11.1 |
| `view.py` | 11.2 |
| `web_search.py` | 11.5 |
| `write.py` | 11.3 |

### utils/（10）
| 文件 | 章节 |
|---|---|
| `__init__.py` | 15 |
| `execution_sandbox.py` | 15 |
| `git.py` | 15 |
| `introspection.py` | 15 |
| `json_utils.py` | 15 |
| `sandbox.py` | 15 |
| `sandbox_access.py` | 15 |
| `schema.py` | 15 |
| `subprocess.py` | 15 |
| `text.py` | 15 |

---

## 附录 B：重点精读文件清单（含每份的拆解要点）

| 文件 | 拆解要点（详见正文） |
|---|---|
| `agent/loop.py` | 单轮事务：落库→投影→调用→结算；权限暂停；tool 过滤；压缩触发三时机；streaming/sync 双实现；limit/cancel/telemetry |
| `context/context_builder.py` | 事实→请求的唯一投影点；checkpoint 摘要插入；tail 边界；tool 序列校验；trimmed 聚合标记；basis_message_id |
| `context/compaction.py` | L1 trim 旧任务 / L2 route 压缩先归档 / L3 换占位；lifecycle 驱动；noop 指纹去重 |
| `context/manager.py` | L1-L4 编排；AUTO/4 触发；熔断；fallback（stronger programmatic / stronger L4） |
| `context/writer.py` | 所有事件落库最后一层；统一补 created_turn/turn_id；工具/规划/压缩事件 schema |
| `context/tool_lifecycle.py` | 纯分类 FRESH/STALE/SUPERSEDED/DERIVED/DUPLICATE；read 覆盖/mutation 失效 |
| `context/models.py` | 事实模型 AgentMessage/MessagePart/SessionView；PartKind 语义 |
| `session/models.py` | SessionRecord/ShareOptions/Transcript/ResumeResult 用户可见模型 |
| `context/store.py` | JSONL append/重放；compaction 替换回放；task_plan revision 校验 |
| `context/archive.py` | 内容寻址不可变存储；占位构造；完整性校验 |
| `context/checkpoint.py` | checkpoint 边界模型 + latest 选择 |
| `providers/base.py` | ChatProvider 抽象（complete/acomplete/astream） |
| `providers/streaming.py` | 同步流→async 队列桥接；tool_call 累积与丢弃策略 |
| `providers/factory.py` | 按 ModelProfile 构造 provider；能力覆盖合并 |
| `permissions/manager.py` | grant→policy 决策链；确认解析；allow-always scope 生成 |
| `permissions/policy.py` | 路径/env/git/shell/网络/MCP 分类决策；AGGRESSIVE 白名单；硬边界 |
| `session/index.py` | 列表索引缓存；写时增量 + 读时懒重建 |
| `session/catalog.py` | 事件→SessionRecord 派生；损坏隔离 |
| `app/router.py` | 组合命令 handler；CommandResult 契约 |
| `app/tui.py` | TUI 外壳；chat/tool/stream 事件接线；权限恢复；picker |
| `app/factory.py` | 装配根：provider+context_manager+tools+MCP+session services |
| `app/runtime.py` | AgentChatRunner；loop 生命周期；guidance；取消 |
| `agent/session.py` | 运行时容器；幂等 tool_result；pending 恢复；system prefix |
| `agent/tool_execution.py` | 权限→执行→结算状态机；后台剥离；并行只读批 |
| `agent/tool_settlement.py` | skipped/interrupted/repair 配对闭合 |
| `agent/execution_evidence.py` | benchmark 修改/验证/后台证据；completion gate |
| `agent/telemetry.py` | turn 结构化计数快照 |
| `agent/stagnation.py` | 相同失败计数阻断 + guidance 注入 |
| `agent/task_boundary_classifier.py` | 隐藏 LLM 分类调用 + JSON 解析 + 降级 |
| `agent/background.py` | 后台任务管理器；占位结果 + notification 协议 |
| `agent/subagent.py` | 角色裁剪子代理；worktree 隔离路径 |
| `app/tui_view.py` | 流式 markdown 分块渲染；跨线程 UI 更新 |
| `context/llm_compact.py` | L4 摘要候选生成 + 边界校验 + commit |
| `context/manager.py`（再列） | 压缩编排 fallback |
| `context/task_boundary.py` | 稳定 task hash + 稳定计数确认 |
| `context/token_budget.py` | 预算/水位计算 |
| `tools/apply_patch.py` | 自定义 patch 语法解析与应用 |
| `tools/review.py` | 写前预览（dry-run 投影 + digest 快照 + stale 检测） |
| `tools/permission_registry.py` | 权限 wrapper preflight/execute |
| `tools/registry.py` | 注册/执行入口；异常→ToolResult |
| `providers/openai_compatible.py` / `anthropic_provider.py` | 协议转换；streaming 事件；tool_calls 解析 |
| `mcp/manager.py` | 同步/异步桥接；后台连接；超时 |
| `context/content/router.py` | L2 路由压缩框架 |
| `input/attachments.py` | 附件 staging + 图片引用提取 |
| `runtime/user_input.py` | UserInputRequest 统一形状 |
| `app/tui_state.py` | TUI 增量状态模型 |
| `tools/types.py` / `session_registry.py` / `builtin.py` | 工具抽象与装配 |
| `config/settings.py` / `config/models.py` | 配置优先级 + Catalog 校验 |