# 项目状态

## 当前阶段

- 里程碑：M1 最小模型调用与 CLI
- 状态：实现与本地验收完成，准备进入 M2
- 版本：v0.0.1
- 下一阶段：M2 只读工具循环

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

## 开放决策

以下决策不影响已完成的 M1，但应在 v0.1.0 稳定发布前确认：

1. 项目名、包名、CLI 命令。
2. 首个真实 Provider 的具体兼容目标和测试服务。
3. 许可证，当前建议 MIT。

最终 TUI 选择可推迟到 M7，不阻塞 M1。

## M2 启动条件

- 创建 M2 里程碑文档包，冻结一个“搜索符号并读取实现”的 Fake 场景。
- 只实现 `Read`、`Glob`、`Grep`，不提前进入 Edit、Shell 和 Session。
- 将唯一 RuntimeRunner 作为模型—工具循环入口。
- 未确认正式名称前继续沿用包 `coding_agent` 和命令 `agent`。
