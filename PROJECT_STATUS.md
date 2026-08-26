# 项目状态

## 当前阶段

- 版本：v0.0.5
- 阶段：Durable Session extension 完成
- 产品源码：3,815 行
- Agent Kernel：1,119 行
- AgentLoop：467 行
- 产品 Python 文件：42 个
- Runtime dependencies：4 个
- 自动化测试：49 项
- 下一阶段：M6 Context strategy 设计评审

## 当前 Kernel

- 一个正式 `AgentLoop`。
- Provider-neutral protocol 与 ChatProvider seam。
- Tool contract、ToolRegistry 和 prepared execution。
- PermissionPolicy/PermissionManager seam。
- SessionBackend、ContextBuilder 和 EventSink seams。
- AgentApplication 与统一 composition root。
- 模型调用、工具轮次、时间和取消限制。

## 当前 Coding preset

- Fake 与 OpenAI-compatible Provider。
- Read、Glob、Grep、Edit、Shell、TodoWrite。
- Workspace 路径边界。
- Edit Diff、digest recheck、stale snapshot 和 atomic replace。
- PowerShell timeout、进程树终止和输出预算。
- plan、standard、bypass 权限模式与 Edit session grant。
- Rich/prompt-toolkit interactive、one-shot 和 JSON CLI。
- In-memory Session 与 append-only JSONL Session。
- Session list/status 和跨进程权限等待恢复。

## M5 Durable Session

- `JsonlSessionStore` 使用一行一个 fact 的 UTF-8 append-only 日志。
- 5 类 SessionEvent 由唯一 reducer 重建 messages、Usage 和 pending permission。
- `PendingPermission` 保存原始 ToolCall、预览 fingerprint 和 Turn 计数。
- resume 在副作用前 append、flush、fsync claim，提供 at-most-once 恢复语义。
- ToolCall 恢复时重新 prepare，并在 confirmation fingerprint 匹配后执行。
- CLI 支持 `--session-dir`、`--list-sessions`、`--resume` 和 `--permission-choice`。
- create、resume 和进程内确认共用当前 Application 与 AgentLoop。

## 里程碑状态

| 里程碑 | 核心交付 | 状态 |
| --- | --- | --- |
| M1 | Provider Loop | 完成 |
| M2 | Tool Loop | 完成 |
| M3 | Application Kernel | 完成 |
| M4 | 可控编码 preset | 完成 |
| M5 | Durable Session | 完成 |

M1–M4 的 Kernel 证据见 [baseline 审计](docs/11-kernel-baseline-audit.md)，M5 的设计与验收见
[M5 文档包](docs/plans/M5/00-scope.md)。

## 已接受硬约束

- 单里程碑只有一个用户故事。
- 单里程碑默认新增产品源码不超过 1,000 行、模块不超过 6 个、领域概念不超过 3 个。
- AgentLoop 不超过 500 行，Kernel 不超过 2,000 行，v0.1.0 产品源码不超过 8,000 行。
- 扩展依赖公开 contract，不依赖 AgentLoop 私有实现。
- 当前里程碑无真实调用路径的类型、事件、配置和 package 不进入产品源码。
- 新 runtime dependency 需要 ADR 和用户批准。

## M6 进入条件

1. 冻结 TokenEstimator 的实际 Provider 策略。
2. 用真实模型测量估算误差和 prompt-too-long 行为。
3. 只选择一个渐进压缩用户故事。
4. 新增产品源码预计不超过 1,000 行。
5. ContextBuilder 继续只生成 ModelRequest，不修改 JSONL Session 事实。

## 发布前开放决策

1. 项目名、Python 包名和 CLI 命令。
2. 首个真实 Provider 的正式兼容目标。
3. 许可证，当前建议 MIT。
