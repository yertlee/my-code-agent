# 项目状态

## 当前阶段

- 版本：v0.0.4
- 阶段：Agent Kernel baseline 收口完成
- 产品源码：3,102 行
- Agent Kernel：1,040 行
- AgentLoop：397 行
- Runtime dependencies：4 个
- 自动化测试：44 项
- 下一阶段：按 Kernel-first 门禁重新设计最小 Durable Session extension

## 当前 Kernel

- 一个正式 `AgentLoop`。
- Provider-neutral protocol 与 ChatProvider seam。
- Tool contract、ToolRegistry 和 prepared execution。
- PermissionPolicy/PermissionManager seam。
- SessionStore、ContextBuilder 和 EventSink seams。
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
- 进程内多 Turn Session 和基础 ContextBuilder。

## Kernel baseline 收口

- 产品架构改为 Agent Kernel + capability extensions。
- composition root 支持替换 SessionStore、ContextBuilder 和 PermissionPolicy。
- TodoWrite 自己持有 TodoStore，不再让所有 ToolContext 依赖规划状态。
- 基础 ContextBuilder、ToolContext、权限策略与 Application 只保留当前真实调用路径。
- 正式文档聚焦当前 Kernel 和按里程碑进入的扩展。
- 新增源码预算、依赖方向、Protocol 宽度和唯一 AgentLoop 自动门禁。
- 新增自定义 Tool extension 纵向测试，AgentLoop 无需修改。

## M1–M4 结论

| 里程碑 | 当前角色 | 收口结论 |
| --- | --- | --- |
| M1 | Provider Kernel | CLI、protocol、Provider seam 保留 |
| M2 | Tool Kernel | ToolRegistry、Workspace、只读工具主线保留 |
| M3 | Application Kernel | AgentLoop、Application、Session/Context seams 保留并移除预置占位层 |
| M4 | Coding preset | Edit/Shell/Permission 安全链路保留，TodoWrite 收敛为自持状态 Tool plugin |

详细证据见 [M1–M4 Kernel baseline 审计](docs/11-kernel-baseline-audit.md)。

## 已接受硬约束

- 单里程碑只有一个用户故事。
- 单里程碑默认新增产品源码不超过 1,000 行、模块不超过 6 个、领域概念不超过 3 个。
- AgentLoop 不超过 500 行，Kernel 不超过 2,000 行，v0.1.0 产品源码不超过 8,000 行。
- 扩展依赖公开 contract，不依赖 AgentLoop 私有实现。
- 当前里程碑无真实调用路径的类型、事件、配置和 package 不进入产品源码。
- 新 runtime dependency 需要 ADR 和用户批准。

## 下一里程碑进入条件

M5 开始前只提交五份以内设计文档，并确认：

1. 唯一故事是“JSONL 重放并继续一次权限等待”。
2. 新增产品源码预计不超过 1,000 行。
3. durable events 不超过 7 类，每类都有 producer 和 reducer。
4. 复用现有 Session 实现的最小闭合骨架。
5. create/resume 共用当前 AgentLoop 和 composition root。

## 发布前开放决策

1. 项目名、Python 包名和 CLI 命令。
2. 首个真实 Provider 的正式兼容目标。
3. 许可证，当前建议 MIT。
