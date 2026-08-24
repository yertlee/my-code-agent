# 项目状态

## 当前阶段

- 里程碑：M2 只读工具循环
- 状态：实现与本地验收完成
- 版本：v0.0.2
- 下一阶段：M3 安全修改与权限

## 已冻结原则

- 产品是可完整讲解的真实 CLI Coding Agent，不追求长期日用平台。
- 只存在一个正式 RuntimeRunner。
- Session Event Log 是持久化事实真相。
- Session、Context、Memory 分离。
- Edit 是唯一文件修改入口。
- P0 工具串行执行。
- 长期记忆默认需要显式确认。
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
- Session 重放、Context 压缩和长期 Memory 设计。
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

## 开放决策

以下决策不影响已完成的 M2，但应在 v0.1.0 稳定发布前确认：

1. 项目名、包名、CLI 命令。
2. 首个真实 Provider 的具体兼容目标和测试服务。
3. 许可证，当前建议 MIT。

最终 TUI 选择可推迟到 M7，不阻塞 M3 至 M6。

## M3 启动条件

- 创建 M3 里程碑文档包，先冻结安全修改、stale snapshot 和权限拒绝场景。
- `Edit` 采用快照、Diff 与原子写入；所有写入继续经过 Workspace。
- P0 仅支持 Windows PowerShell，standard 模式下 Shell 每次确认。
- 不提前进入 Session JSONL、Context 压缩和 Memory。
- 未确认正式名称前继续沿用包 `coding_agent` 和命令 `agent`。
