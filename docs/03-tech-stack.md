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
| 完整 TUI | Textual | P1 |
| 异步运行 | anyio | 暂定 |
| HTTP/Provider SDK | 厂商官方 SDK | 已接受 |
| Session 事实 | JSONL | 已接受 |
| P0 Session 目录 | 扫描 JSONL header/tail | 已接受 |
| Memory/可重建索引 | SQLite | M6/P1 |
| Token 估算 | Provider profile + 可选 tiktoken + 保守 UTF-8 fallback | 已接受 |
| 配置 | TOML + 环境变量 | 已接受 |
| 测试 | pytest | 已接受 |
| 代码质量 | Ruff + basedpyright | 暂定 |

## 2. 为什么选择 Python 3.12

- 与三个参考项目的主要语言一致，适合源码对照学习。
- 类型系统、异步生态、终端 UI 和模型 SDK 足够成熟。
- 避免要求使用过新的 Python 3.14，降低安装门槛。
- 可以用 dataclass 表达内部协议，用 Pydantic 管理不可信边界。

## 3. 为什么不用 Agent Framework 承担主循环

本项目可以使用 Pydantic，但不以 Pydantic AI、LangGraph 或 Agents SDK 作为核心 RuntimeRunner。

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

### SQLite

只用于索引和可查询派生数据：

- Memory 作用域、标签、来源和全文检索；
- Artifact 元数据。

P0 的 Session list/resume/status 直接扫描 JSONL 的首尾事件。SQLite 到 M6 才引入；以后即使缓存 Session 元数据，也只能作为可删除、可重建的读优化。

SQLite 不是 Session 事实的第二写入源。索引损坏时必须能从 JSONL 重建。

Memory 的第一版“全文搜索”使用有界 Python Unicode substring/casefold 或 SQLite `LIKE`，不把 FTS5 中文分词能力当作正确性前提。FTS、trigram 或 Embedding 只能在测量真实语料后作为后续优化。

## 6. Token 计数与误差策略

ContextEngine 通过 `TokenEstimator` 端口计数，模型配置必须声明 `context_window`、估算方式和安全余量：

1. Provider 提供输入计数接口时，可在接近高水位或调试模式下做远端精确预检。例如 OpenAI Responses 提供 [`POST /responses/input_tokens`](https://developers.openai.com/api/reference/typescript/resources/responses/subresources/input_tokens)；该能力属于 Provider capability，不假设所有兼容服务都实现。
2. 已知 OpenAI encoding 使用可选 `tiktoken` 本地估算。
3. 未知 OpenAI-compatible 或本地模型使用保守 UTF-8 字节估算，加协议开销和默认 25% 安全余量，并把结果标记为 approximate。
4. Provider 响应返回的 Usage 写入 Session，用于记录估算误差和调整模型 profile；它只能校准下一次请求，不能替代当前请求的预算。OpenAI Responses 的响应 Usage 包含 input/output/total tokens，见[官方响应字段](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)。

高低水位基于“估算值 + 安全余量”判断，`prompt_too_long` 仍保留一次强制压缩恢复。估算器不得谎称跨模型精确。

## 7. UI 策略

- P0 使用 prompt-toolkit + Rich，保持输入、流式输出和权限确认简单透明。
- P1 引入 Textual，但 TUI 只能消费 RuntimeEvent 和调用 Application Command。
- RuntimeRunner 不得 import Rich、prompt-toolkit 或 Textual。

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
- POSIX 支持进入 P1，并要求独立 CI 与行为场景，不以“理论可运行”宣称兼容。

## 10. 暂缓技术

- 向量数据库：作用域、全文搜索和显式标签足够支撑 P1 Memory。
- Docker 沙箱：权限策略不是 OS 隔离，首版如实说明边界。
- Redis、消息队列和后台服务：单机 CLI 不需要分布式基础设施。
- ORM：SQLite 查询保持少量显式 SQL，避免为了简单索引引入额外层。
