# 项目状态

## 当前阶段

- 里程碑：M4 写工具与权限
- 状态：完成，本地验收通过
- 版本：v0.0.4
- 下一阶段：M5 Session 与恢复

## 已冻结原则

- 产品是可完整讲解的真实 CLI Coding Agent，不追求长期日用平台。
- 只存在一个正式 AgentLoop。
- Session Event Log 是持久化事实真相。
- Session、Context、Memory 分离。
- Edit 是唯一文件修改入口。
- P0 工具串行执行。
- 长期 Memory 必须具有来源、作用域和用户控制能力。
- 核心模型—工具循环不交给 Agent Framework。
- P0 只保证 Windows；POSIX 为后续兼容目标。
- P0 `Shell`（PowerShell 实现）在 standard 模式下一律逐次确认，不做“安全命令”自动放行。
- P0 Session 列表通过扫描 JSONL 得到，不依赖 SQLite。

## M0 已交付

- 产品章程和非目标。
- P0/P1/P2 功能范围。
- 模块边界、依赖方向和标准 Turn Trace。
- 技术栈和 Provider 演进策略。
- SessionEvent/UiEvent、停止原因和错误恢复规则。
- Session 重放设计，以及 Context 与 Memory 的职责边界和阶段约束。
- 工具、权限、Workspace 和安全边界。
- M1 至 M8 路线图。
- 测试、故障注入和发布门禁。
- ADR 与开发治理规则。

## M1 已交付

- Python 3.12、uv、setuptools 和 `agent` console script。
- Provider-neutral message/request/stream/usage/error/result 类型。
- 可脚本化 Fake Provider，无需网络或 API Key。
- OpenAI-compatible Chat Completions 流式 Provider。
- 普通文本与 schema v1 `--json` 输出。
- 认证、限流、网络、上下文过长等错误分类。
- Windows UTF-8 stdout/stderr 输出。
- 9 个确定性测试、Ruff、basedpyright、构建和全新环境安装验证。
- Windows GitHub Actions CI。

## M2 已交付

- 唯一 RuntimeRunner；M1 `run_prompt` 仅作为兼容包装。
- 固定根目录的 Workspace 与路径逃逸防护。
- `Read`、`Glob`、`Grep`、Tool Registry、Pydantic 参数校验和统一输出预算。
- 8 次模型调用、6 个工具轮次和 120 秒总时间默认限制，以及明确的取消终态。
- Fake Provider 的 `Grep → Read → final` 确定性场景。
- OpenAI-compatible 流式 tool-call 参数累积。
- DeepSeek thinking tool turn 的 `reasoning_content` 保留与回放。
- 文本工具活动展示与 schema v1 JSON 中的模型/工具轮次统计。
- 21 个无网络测试覆盖正常循环、错误参数、工作区边界和限制终态。

## M3 已交付

- `app/agent/runtime/session/context/memory/permissions` 完整包边界与 composition root。
- 唯一 `AgentLoop`，one-shot 和交互式 CLI 共用同一装配路径。
- Rich/prompt-toolkit 交互式 CLI，以及 `/help`、`/exit`、`/quit`。
- 多 Turn 内存 Session，后续请求能够看到同一进程内的完整对话和工具结果。
- 基础 ContextBuilder、EmptyMemoryRetriever 和 ReadOnlyPermissionPolicy 进入真实调用链。
- 结构化 RuntimeEvent、协作式 CancellationToken 和 Application 级 Provider 生命周期。
- Windows 非终端重定向输入回退，交互场景可以被脚本与 CI 驱动。
- 28 个无网络测试，覆盖 AgentLoop、模块边界、Application、多 Turn 和交互命令。

## M4 已交付

- 单一 `Edit` 工具支持 UTF-8 文件创建、精确替换与删除，并生成可信 unified diff。
- 写入前后摘要复查、stale snapshot 拒绝与同目录临时文件原子替换。
- `plan`、`standard`、`bypass` 三种权限模式，以及 Edit 精确路径 Session grant。
- AgentLoop 权限暂停/继续协议；CLI 只回传 request ID 与选择，不重构模型工具参数。
- Windows PowerShell 执行器，包含 Workspace cwd、超时、进程树终止和独立输出预算。
- 带 optimistic revision 和状态约束的进程内 TodoWrite。
- plain/interactive 权限确认、Diff 活动展示，以及 JSON waiting/退出码 3 契约。
- 39 个无网络测试覆盖权限、写入、stale、Shell、Todo 和 M1–M3 回归路径。

## 开放决策

以下决策不影响已完成的 v0.0.4，但应在 v0.1.0 稳定发布前确认：

1. 项目名、包名、CLI 命令。
2. 首个真实 Provider 的具体兼容目标和测试服务。
3. 许可证，当前建议 MIT。

v0.1.0 使用 Rich/prompt-toolkit CLI；Textual TUI 后续单独评审。

## M5 启动条件

- JSONL 是唯一持久化事实，SessionView 只能由事件重放得到。
- 暂停即返回；AgentLoop 不跨用户等待持有调用栈。
- M4 的 pending permission 语义迁移为 durable event，重启后恢复同一请求且不重复副作用。
- `session list` 在 P0 扫描 JSONL 目录，SQLite 保留到 Memory 检索阶段。
- 先冻结 tool started 后进程中断的 settlement 与 uncertain 状态，再实现恢复执行。
