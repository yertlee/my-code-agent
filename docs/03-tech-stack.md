# 主要技术栈

## 1. 选型结论

| 类别 | 选择 | 状态 |
| --- | --- | --- |
| 语言 | Python 3.12 | 已接受 |
| 包与环境 | `uv` + `pyproject.toml` | 已接受 |
| 构建后端 | setuptools | 暂定 |
| 类型与校验 | dataclass + Pydantic v2 | 已接受 |
| CLI 参数 | argparse | 暂定 |
| 基础交互 | prompt-toolkit + Rich | 已接受 |
| 完整 TUI | Textual | v0.1.0 之后 |
| 异步运行 | anyio | 暂定 |
| HTTP/Provider SDK | 厂商官方 SDK | 已接受 |
| Session 事实 | JSONL | 已接受 |
| P0 Session 目录 | 扫描 JSONL header/tail | 已接受 |
| Memory 存储与索引 | M7 设计评审确定 | open |
| Token 估算 | M6 设计评审确定 | open |
| 配置 | TOML + 环境变量 | 已接受 |
| 测试 | pytest | 已接受 |
| 代码质量 | Ruff + basedpyright | 暂定 |

## 2. 为什么选择 Python 3.12

- 与三个参考项目的主要语言一致，适合源码对照学习。
- 类型系统、异步生态、终端 UI 和模型 SDK 足够成熟。
- 避免要求使用过新的 Python 3.14，降低安装门槛。
- 可以用 dataclass 表达内部协议，用 Pydantic 管理不可信边界。

## 3. 为什么不用 Agent Framework 承担主循环

本项目可以使用 Pydantic，但不以 Pydantic AI、LangGraph 或 Agents SDK 作为核心 AgentLoop。

原因不是这些框架不可用，而是它们会替项目承担部分关键教学内容：

- 模型与工具如何交替；
- 工具调用如何暂停并恢复；
- 历史如何转换为 Provider 消息；
- 中断工具如何结算；
- 循环为什么停止。

本项目的核心价值正是把这些机制写出来。框架可以作为后续对比实验，而不是正式运行时。

## 4. Provider 策略

内部只依赖统一协议：

```text
ModelRequest
ModelResponse
ModelStreamEvent
ToolDefinition
ToolCall
ToolResult
TokenUsage
ProviderCapabilities
ProviderErrorKind
```

实现顺序：

1. OpenAI-compatible Chat Completions：覆盖代理服务和本地兼容模型，协议易于讲解。
2. OpenAI Responses：支持其原生输入项、函数工具、流式事件和推理状态。
3. Anthropic Messages：证明内部协议没有被 OpenAI 请求结构绑定。

OpenAI Responses 支持函数工具、流式响应、`previous_response_id` 和远端 conversation；本项目仍以本地 Event Log 为恢复真相，Provider 状态只作为优化，不作为必要依赖。官方接口参考：[Create a model response](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)。

## 5. 持久化策略

### JSONL

用于 Session 事实：

- 易于人工阅读和教学展示；
- 只追加，崩溃时修复尾部记录相对直接；
- 每个事件可独立版本化；
- 适合重放和测试快照。

P0 的 Session list/resume/status 直接扫描 JSONL，不依赖额外数据库。长期 Memory 的持久化与
检索索引在 M7 设计评审中确定，并继续保持与 Session 恢复事实分离。

## 6. Token 计数与误差策略

ContextEngine 必须在请求前得到带误差说明的 Token 估算，并为模型输出、工具 Schema 和协议
开销预留空间。具体 tokenizer、Provider 计数能力、未知模型 fallback、安全余量与高低水位在
M6 设计评审中通过目标模型和固定长会话场景确定。

## 7. UI 策略

- P0 使用 prompt-toolkit + Rich，保持输入、流式输出和权限确认简单透明。
- 后续引入 Textual 时，TUI 只能消费 RuntimeEvent 和调用 Application Command。
- AgentLoop 不得 import Rich、prompt-toolkit 或 Textual。

## 8. 配置与秘密

```text
CLI flags
  > <project>/agent.toml
  > user config
  > built-in defaults
```

- API Key 只通过环境变量或操作系统秘密管理读取。
- `config show` 只显示变量名和非敏感配置，不打印实际 Secret。
- Provider-specific 字段保留在 Provider Profile 内，不进入 Session Domain Model。

## 9. 平台范围

- P0 只保证 Windows 10/11 和 PowerShell 进程语义。
- 保留窄 `ShellAdapter` 端口隔离命令启动、取消和进程树终止，但不提前实现 POSIX 分支。
- POSIX 支持在 v0.1.0 后进入独立里程碑，并要求独立 CI 与行为场景。

## 10. 暂缓技术

- 向量数据库：作用域、全文搜索和显式标签足够支撑 P1 Memory。
- Docker 沙箱：权限策略不是 OS 隔离，首版如实说明边界。
- Redis、消息队列和后台服务：单机 CLI 不需要分布式基础设施。
- ORM：在 Memory 存储方案确定前不引入。
