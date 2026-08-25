# Coding Agent（项目名待定）

一个本地优先、单 Agent、可完整讲解的 CLI Coding Agent。

本项目的目标不是替代 Claude Code，也不是构建企业级 Agent 平台。它要在有限规模内真实展示：模型如何读取代码、调用工具、修改文件、请求权限、压缩上下文、持久化会话、从中断恢复，并把整个执行过程清楚地映射到源码、文档和测试。

当前阶段：[M4 写工具与权限已完成](PROJECT_STATUS.md)。Agent 已能在统一 `AgentLoop` 中生成
Diff、暂停请求权限、执行可信写入和 PowerShell 验证；M5 将把内存 Session 升级为可跨进程恢复的
JSONL 事实流。

## 快速开始

需要安装 [uv](https://docs.astral.sh/uv/)，项目会自动使用隔离的 Python 3.12：

```powershell
uv sync --dev --locked
uv run agent
uv run agent -p "找到 ProviderErrorKind 的定义" --fake-scenario readonly
uv run agent -p "找到 ProviderErrorKind 的定义" --fake-scenario readonly --json
uv run agent -p "创建演示文件并验证" --fake-scenario write
```

写入演示会依次展示 Edit Diff 和 PowerShell 请求。standard 模式下可选择 `deny`、`allow_once`，
Edit 还支持对同一路径 `allow_session`。也可以显式使用只规划或自动批准模式：

```powershell
uv run agent -p "检查并修改项目" --permission-mode plan
uv run agent -p "创建演示文件并验证" --fake-scenario write --permission-mode bypass
```

`--json` 不读取权限输入；需要确认时返回 `status=waiting`、`pending_input` 和退出码 3。M5 会为该
等待状态增加跨进程恢复入口。

默认使用无需网络的 Fake Provider。连接 OpenAI-compatible 服务时：

```powershell
$env:OPENAI_API_KEY = "..."
$env:CODING_AGENT_MODEL = "your-model"
$env:OPENAI_BASE_URL = "https://your-service.example/v1"  # 官方 OpenAI 可省略
uv run agent -p "你好" --provider openai-compatible
```

API Key 只从 `--api-key-env` 指定的环境变量读取，不提供明文 Key 参数。部分兼容服务不支持
流式 Usage，可增加 `--no-stream-usage`。

DeepSeek 等 OpenAI-compatible 服务可以使用独立的 Key 环境变量：

```powershell
$secureKey = Read-Host "DeepSeek API Key" -AsSecureString
$env:DEEPSEEK_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
$env:CODING_AGENT_MODEL = "your-deepseek-model"
uv run agent -p "概括这个项目的运行时入口" `
  --provider openai-compatible `
  --base-url "https://api.deepseek.com" `
  --api-key-env DEEPSEEK_API_KEY `
  --no-stream-usage
Remove-Variable secureKey
```

## M4 代码入口

- CLI：`src/coding_agent/cli.py`
- Application 与装配：`src/coding_agent/app/`
- 唯一 Agent Loop：`src/coding_agent/agent/loop.py`
- 运行活动与取消：`src/coding_agent/runtime/`
- 内存 Session 与 Todo revision：`src/coding_agent/session/`
- 基础 Context 与 Memory 边界：`src/coding_agent/context/`、`src/coding_agent/memory/`
- 权限模式、决策与 Session grant：`src/coding_agent/permissions/`
- Provider-neutral 类型：`src/coding_agent/protocol/models.py`
- OpenAI-compatible Provider：`src/coding_agent/providers/openai_compatible.py`
- Workspace 边界：`src/coding_agent/workspace/workspace.py`
- Read/Glob/Grep/Edit/Shell/TodoWrite 与注册表：`src/coding_agent/tools/`
- M4 设计、验收与 Closeout：`docs/plans/M4/`

## 项目主线

```text
用户任务
  -> CLI 接收输入
  -> 唯一 AgentLoop 开始一轮任务
  -> Session Event Log 记录事实
  -> ContextEngine 构造受预算约束的模型视图
  -> Provider 调用模型
  -> ToolOrchestrator 校验、授权并执行工具
  -> 工具结果写回 Event Log
  -> 模型继续或产生最终答案
  -> CompletionGate 检查任务是否可以结束
  -> CLI 展示结果，会话可被恢复
```

## 产品原则

- 真实可运行，但保持端到端可读。
- 只保留一个正式 Agent Loop。
- 安全策略由代码执行，不依赖 Prompt 承诺。
- Session 是事实；Context 和 Memory 都是派生视图。
- 工具调用、权限暂停、中断与恢复必须有明确状态。
- 功能、设计文档和验证测试同时交付。
- 优先完成单 Agent，不用多 Agent 掩盖基础设计问题。

## 预期能力

- Rich/prompt-toolkit 交互式 CLI 与 one-shot 模式
- 流式模型输出和工具活动展示
- `Read`、`Glob`、`Grep`、`Edit`、`Shell`、`TodoWrite`
- 文件 Diff、权限确认和项目根目录限制
- 多轮 Session、会话列表、恢复和取消
- Token 预算、工具输出 Artifact 和多级上下文压缩
- 显式长期记忆和带来源的记忆候选
- Skills 渐进加载
- OpenAI-compatible Provider，后续增加 OpenAI Responses 与 Anthropic
- Fake Provider 测试、失败注入和小型任务评测集
- v0.1.0 后独立设计 Textual TUI

## 明确不做

- 企业账号、团队协作和云端控制台
- IDE 插件或远程 Worker
- 默认多 Agent、Agent Team 或复杂 DAG
- OS 级安全沙箱
- 自动自我修改或自动进化 Skills
- 大规模向量数据库和通用 RAG 平台

## 文档索引

1. [产品章程](docs/00-product-charter.md)
2. [功能范围](docs/01-scope-and-features.md)
3. [总体架构](docs/02-architecture.md)
4. [技术栈](docs/03-tech-stack.md)
5. [运行时协议](docs/04-runtime-spec.md)
6. [Session、Context 与 Memory](docs/05-state-context-memory.md)
7. [工具、权限与安全](docs/06-tools-permissions-security.md)
8. [版本路线图](docs/07-roadmap.md)
9. [测试与评测](docs/08-testing-and-evaluation.md)
10. [架构决策记录](docs/09-decisions.md)
11. [开发治理与防跑偏机制](docs/10-development-governance.md)

## 参考项目

- [MyCodeAgent](https://github.com/YYHDBL/MyCodeAgent)：单循环、恢复真相、工具边界与运行时约束参考。
- [Kapybara](https://github.com/BeautyyuYanli/Kapybara)：作用域记忆、父子记忆、偏好与结构化任务总结参考。

项目会把借鉴到的思想落实为一致的接口、状态模型、失败语义和验收测试。
