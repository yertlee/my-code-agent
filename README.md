# Coding Agent（项目名待定）

一个以可阅读 Agent Kernel 为核心、通过能力扩展组成 Coding preset 的本地 CLI Agent。

项目先把 `CLI → Application → AgentLoop → Provider/Tool → TurnResult` 做成一条可运行、可观察、
可测试的主线，再通过窄 contracts 增加 Session、Context、Memory、Provider 和 Tool plugins。目标是
让学习者既能完整读懂一次 Agent 活动，也能在不修改 AgentLoop 的情况下安装新能力。

当前阶段：[Memory 主线已闭环](PROJECT_STATUS.md)：默认 Coding preset 已支持读取、搜索、Diff、
权限确认、文件修改、PowerShell、TodoWrite、JSONL 会话恢复、可观察的上下文压缩，以及跨会话项目记忆。

## 快速开始

需要安装 [uv](https://docs.astral.sh/uv/)：

```powershell
uv sync --dev --locked
uv run agent
uv run agent -p "找到 ProviderErrorKind 的定义" --fake-scenario readonly
uv run agent -p "创建演示文件并验证" --fake-scenario write
uv run agent -p "找到 ProviderErrorKind 的定义" --fake-scenario readonly --json
uv run agent -p "概括项目结构" --context-window 16384
```

持久化一次权限等待并在新进程恢复：

```powershell
uv run agent -p "创建演示文件" --fake-scenario write `
  --session-dir .coding-agent/sessions --json
uv run agent --list-sessions --session-dir .coding-agent/sessions --json
uv run agent --resume <session_id> --permission-choice allow_once `
  --session-dir .coding-agent/sessions --fake-scenario write --json
```

`--session-dir` 相对于 `--cwd` 解析。Session 文件是一行一个事实的 UTF-8 JSONL；恢复权限时先持久化
claim，再执行经过重新 prepare 和预览校验的工具调用。

## Context 投影

默认 Context window 为 32k token；可用 `CODING_AGENT_CONTEXT_WINDOW` 设置进程默认值，或用
`--context-window` 为单次运行覆盖。CLI 参数优先级最高。

超长工具输出会在模型请求前收缩，历史内容不足时按完整工作回合淘汰。`--json` 的结果包含 `context`
摘要（预算、压缩数量、淘汰轮次与超限状态）；终端仅在发生压缩或超限时输出 `[context]` 行。

## Project Memory

指定 `--memory-dir` 后，Agent 会把成功的项目配置读取和 Shell 命令记录为带证据的项目事实，并在新
Session 中按当前任务关键词召回。召回内容以低权限 Context 注入，当前工具结果始终具有更高可信度。

```powershell
uv run agent --remember "项目使用 uv 管理 Python 依赖" `
  --memory-kind convention --memory-dir .coding-agent/memory
uv run agent -p "这个项目怎样管理依赖？" `
  --memory-dir .coding-agent/memory --json
uv run agent --list-memory --memory-dir .coding-agent/memory
uv run agent --inspect-memory <memory_id> --memory-dir .coding-agent/memory --json
uv run agent --forget-memory <memory_id> --memory-dir .coding-agent/memory
```

默认实现是 append-only JSONL Ledger、证据驱动 Writer 和可解释的关键词 Retriever。交互模式还支持
`/remember`、`/memory list`、`/memory inspect` 与 `/forget`。

### Writer 策略对比

`evidence` 是零额外模型调用的默认 Writer；`llm` 使用当前 Provider 从成功的配置文件 Read 与 Shell
结果中提取更丰富的结构化事实。LLM 候选必须引用真实 evidence part，解析或 Provider 失败只进入
Memory 观测结果，不中断 Agent 任务。

```powershell
uv run agent -p "读取 pyproject.toml 并分析项目约定" `
  --provider openai-compatible --model deepseek-v4-flash `
  --base-url "https://api.deepseek.com" --api-key-env DEEPSEEK_API_KEY `
  --no-stream-usage --memory-dir .coding-agent/memory-llm --memory-writer llm --json
```

`TurnResult.memory` 会分别报告 `proposed`、`accepted`、`rejected`、`written`、
`writer_model_calls`、`writer_usage` 与 `write_errors`。固定 Writer 对比案例可直接运行：

```powershell
uv run python scripts/evaluate_memory_writers.py --writer evidence
uv run python scripts/evaluate_memory_writers.py --writer llm `
  --model deepseek-v4-flash --base-url https://api.deepseek.com `
  --api-key-env DEEPSEEK_API_KEY
```

评测 JSON 同时包含每条候选的 kind、key、content、confidence、evidence part 与
`candidate_delta`，便于人工审查重复和过度提取。

写入演示会展示 Edit Diff 和 PowerShell 请求。standard 模式支持 `deny`、`allow_once`，Edit 还支持
同一路径 `allow_session`：

```powershell
uv run agent -p "创建演示文件并验证" --fake-scenario write
uv run agent -p "检查项目" --permission-mode plan
uv run agent -p "创建演示文件并验证" --fake-scenario write --permission-mode bypass
```

## 真实 Provider

连接 OpenAI-compatible 服务：

```powershell
$env:OPENAI_API_KEY = "..."
$env:CODING_AGENT_MODEL = "your-model"
$env:OPENAI_BASE_URL = "https://your-service.example/v1"
uv run agent -p "概括这个项目的 Agent Kernel" --provider openai-compatible
```

DeepSeek 示例：

```powershell
$secureKey = Read-Host "DeepSeek API Key" -AsSecureString
$env:DEEPSEEK_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
$env:CODING_AGENT_MODEL = "your-deepseek-model"
uv run agent -p "概括这个项目的 Agent Kernel" `
  --provider openai-compatible `
  --base-url "https://api.deepseek.com" `
  --api-key-env DEEPSEEK_API_KEY `
  --no-stream-usage
Remove-Variable secureKey
```

API Key 只从 `--api-key-env` 指定的环境变量读取。

## Agent Kernel

```text
CLI / API
  -> AgentApplication
  -> AgentLoop
       -> ChatProvider
       -> ContextBuilder
       -> ToolRegistry -> Tool plugins
       -> PermissionManager -> PermissionPolicy
       -> SessionBackend
       -> MemoryService -> Ledger / Writer / Retriever
       -> ContextBuilder -> ContextStrategy
       -> EventSink
  -> TurnResult
```

Kernel 代码入口：

- [AgentLoop](src/coding_agent/agent/loop.py)
- [公共协议](src/coding_agent/protocol/models.py)
- [Tool contract](src/coding_agent/tools/base.py) 与 [ToolRegistry](src/coding_agent/tools/registry.py)
- [Application](src/coding_agent/app/application.py) 与 [composition root](src/coding_agent/app/factory.py)
- [Runtime events/cancellation](src/coding_agent/runtime/)

内置扩展：

- Provider adapters：[providers](src/coding_agent/providers/)
- Coding tools：[tools](src/coding_agent/tools/)
- Permission policy：[permissions](src/coding_agent/permissions/)
- In-memory/JSONL Session：[session](src/coding_agent/session/)
- Basic Context：[context](src/coding_agent/context/)
- Project Memory：[memory](src/coding_agent/memory/)
- CLI presentation：[app](src/coding_agent/app/)

## 扩展方式

当前插件模型是普通 Python contract + Registry + composition：

```python
class MyTool:
    definition = ToolDefinition(...)

    async def execute(self, arguments, context):
        return ToolExecution("result")

tools = ToolRegistry((*coding_tools(), MyTool()))
```

Provider、SessionBackend、ContextStrategy、MemoryService、PermissionPolicy 和 EventSink 也可以在
composition root 替换。
轻量 package discovery 与外部 Tool plugin 示例在 v0.1.0 收口阶段交付。

## 硬性可读性门禁

- AgentLoop ≤ 500 行。
- Agent Kernel ≤ 2,000 行。
- v0.1.0 产品源码 ≤ 8,000 行，达到 6,000 行先复查范围。
- 单里程碑默认新增产品源码 ≤ 1,000 行、模块 ≤ 6 个、领域概念 ≤ 3 个。
- 当前里程碑没有真实调用路径的 contract、event、配置和 package 不进入产品源码。
- 自动测试检查源码预算、runtime dependencies、唯一 AgentLoop 和扩展导入方向。

完整规则见[开发治理](docs/10-development-governance.md)。

## 文档

1. [产品章程](docs/00-product-charter.md)
2. [功能范围与扩展路线](docs/01-scope-and-features.md)
3. [Agent Kernel 与扩展架构](docs/02-architecture.md)
4. [技术栈](docs/03-tech-stack.md)
5. [Kernel Runtime](docs/04-runtime-spec.md)
6. [Session、Context 与 Memory 扩展边界](docs/05-state-context-memory.md)
7. [Tool plugins、权限与 Workspace](docs/06-tools-permissions-security.md)
8. [Kernel-first 路线图](docs/07-roadmap.md)
9. [测试与可读性验证](docs/08-testing-and-evaluation.md)
10. [架构决策](docs/09-decisions.md)
11. [Kernel-first 开发治理](docs/10-development-governance.md)
12. [M1–M4 Kernel baseline 审计](docs/11-kernel-baseline-audit.md)

## 架构参考

- [DeepSeek Harness Architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md)：能力作为 plugins、默认 Agent Loop 与可组合服务边界。
- [MyCodeAgent](https://github.com/YYHDBL/MyCodeAgent)：单循环、恢复真相与工具边界。
- [Kapybara](https://github.com/BeautyyuYanli/Kapybara)：作用域记忆与结构化任务总结。
