# coding-agent 交接文档

> 最后更新：2026-08-27，M7.1 Memory Writer Strategy Comparison 实现完成。

## 1. 产品与当前版本

`coding-agent` 是面向学习与讲解的本地 CLI coding agent。核心阅读路径是：

```text
CLI -> AgentApplication -> AgentLoop
    -> SessionBackend
    -> MemoryService
    -> ContextBuilder
    -> ChatProvider / ToolRegistry / PermissionManager
    -> TurnResult
```

当前版本 v0.0.8。源码保持单一 AgentLoop 和窄 contract；Coding preset 提供真实文件工具、权限确认、
durable Session、确定性 Context 压缩与项目记忆。

## 2. 已完成主线

- M1 Provider Loop：Fake/OpenAI-compatible Provider、流式与非流式响应、错误分类。
- M2 Tool Loop：Read/Glob/Grep 和模型—工具循环。
- M3 Application Kernel：one-shot/interactive 共用 Application 与 AgentLoop。
- M4 Coding preset：Edit、Shell、TodoWrite、Diff、权限与 stale snapshot。
- M5 Durable Session：append-only JSONL、reducer、权限等待与跨进程 resume。
- M6 Context strategy：预算估算、工具输出压缩、完整回合淘汰、超限停止和投影摘要。
- M7 Project Memory：MemoryService、JSONL Ledger、证据 Writer、关键词 Retriever、跨会话召回与管理。
- M7.1 Writer comparison：Evidence/LLM Writer 切换、结构化证据校验、指标输出与固定评测案例。

## 3. 当前架构不变量

- `AgentLoop` 只有一个，交互、one-shot 与 resume 共享同一运行语义。
- Session 是对话事实账本；Context 是单次模型投影；Memory 是独立生命周期的项目知识。
- Context 压缩不修改 Session；Memory 不参与权限决定、Workspace 边界和 Tool 恢复。
- AgentLoop 只依赖 `MemoryService`，Ledger/Writer/Retriever 是默认服务的内部组合点。
- 项目记忆按来源保存，召回时作为低权限事实；当前工具证据优先。
- AgentLoop ≤ 500 行、Kernel ≤ 2,000 行、v0.1.0 产品源码 ≤ 8,000 行。

## 4. M7 代码入口

- `src/coding_agent/memory/base.py`：MemoryService/Ledger/Writer/Retriever contracts。
- `src/coding_agent/memory/models.py`：候选、记录、证据、查询、命中与召回 DTO。
- `src/coding_agent/memory/jsonl.py`：append-only JSONL Ledger 与重放。
- `src/coding_agent/memory/default.py`：默认 Writer、Retriever 和 MemoryService。
- `src/coding_agent/memory/assisted.py`：结构化 LLM Writer 与 evidence 校验。
- `src/coding_agent/context/builder.py`：MemoryRecall 的低权限注入。
- `src/coding_agent/agent/loop.py`：每轮召回与工具结果观察。
- `src/coding_agent/app/memory_commands.py`：one-shot 记忆管理命令。

## 5. 验证与运行

```powershell
uv sync --dev --locked
uv run ruff check .
uv run basedpyright
uv run pytest
uv run agent --version
```

手动记忆和跨进程召回：

```powershell
uv run agent --remember "项目使用 uv 管理 Python 依赖" `
  --memory-kind convention --memory-dir .coding-agent/memory
uv run agent -p "项目如何管理依赖？" --memory-dir .coding-agent/memory --json
uv run agent --list-memory --memory-dir .coding-agent/memory
uv run python scripts/evaluate_memory_writers.py --writer evidence
```

## 6. 下一步

首次 DeepSeek 固定评测已保存到 `evals/results/`。使用增强后的同一命令复跑，审查
`successful_test_command` 的两条候选内容与 `candidate_delta`；完成候选质量判断后，再决定是否进入
Retriever 策略比较。所有实现继续复用现有 contract 与 AgentLoop。

发布前还需确定项目名、包名、CLI 命令和许可证。
