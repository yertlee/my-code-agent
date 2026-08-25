# 项目状态

## 当前阶段

- 里程碑：M3 架构骨架与交互式 CLI
- 状态：完成，本地验收通过
- 版本：v0.0.3
- 下一阶段：M4 写工具与权限

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

## 开放决策

以下决策不影响已完成的 v0.0.3，但应在 v0.1.0 稳定发布前确认：

1. 项目名、包名、CLI 命令。
2. 首个真实 Provider 的具体兼容目标和测试服务。
3. 许可证，当前建议 MIT。

v0.1.0 使用 Rich/prompt-toolkit CLI；Textual TUI 后续单独评审。

## M4 启动条件

- 先冻结 Edit 的 preview/snapshot/stale-write 行为和失败场景。
- 先冻结 PermissionRequest、模式、grant 和暂停返回协议。
- Shell 继续使用 PowerShellExecutor，standard 模式每次 ASK。
- 保持 M3 composition root、AgentLoop、RuntimeEvent 和多 Turn Session 行为兼容。
