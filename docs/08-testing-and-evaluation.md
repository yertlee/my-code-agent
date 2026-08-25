# 测试与评测策略

## 1. 测试目标

测试证明各模块合同、完整 CLI 路径、副作用边界和恢复行为。测试替身用于控制外部响应与故障，
产品正确性由模块断言、临时仓库状态、Session 事实和用户入口共同验证。

## 2. 测试分层

| 层级 | 目标 | 代表范围 |
| --- | --- | --- |
| Unit | 单个纯模块和状态转换 | reducer、budget、policy、scope、freshness |
| Contract | 跨边界 DTO 和 adapter | Provider、Tool Schema、Session Event |
| Integration | 多模块协作 | AgentLoop、Workspace、Permission、Session、Context |
| E2E | 用户入口与真实文件状态 | CLI 读取、修改、确认、恢复、JSON 输出 |
| Regression | 已发现缺陷和不变量 | stale write、orphan tool、uncertain recovery |
| Real-provider smoke | 实际服务兼容性 | 发布前人工运行固定任务 |

## 3. 模块测试范围

### Provider

- 文本和 reasoning 流式 delta；
- Tool Call 参数累积与多工具消息；
- Usage；
- 认证、限流、网络、超时和 prompt-too-long；
- 厂商字段不会进入领域层。

### Agent Loop

- 纯文本、单工具和多工具；
- ToolResult 回传后的继续请求；
- 权限等待、拒绝、允许和继续；
- 模型调用、工具轮次、总时间和取消；
- CompletionGate 与停止原因。

### Tool、Workspace 与 Permission

- Read/Glob/Grep/Edit/Shell/Todo 的正常和错误行为；
- Schema 校验与结构化 ToolResult；
- 路径穿越、绝对路径、symlink 和敏感目录；
- Diff、snapshot recheck、atomic replace；
- allow/ask/deny、grant scope 和权限模式；
- Shell timeout、输出截断和进程树终止。

### Session

- Event 编解码、sequence 和 schema version；
- append、尾部损坏和并发写保护；
- Reducer 与 SessionView；
- pending permission 与 user input；
- started 工具恢复为 uncertain；
- completed 副作用不会重放。

### Context

- 详细测试集在 M6 设计评审时冻结；
- 至少覆盖预算、消息合法性、长结果管理、压缩、恢复和来源关系；
- 压缩不能改变 Session 原始事实。

### Memory

- 详细测试集在 M7 设计评审时冻结；
- 至少覆盖用户控制、作用域、来源变化、过期、检索和删除；
- Memory 故障不能破坏 Session 恢复或权限边界。

### CLI

- one-shot 和交互模式共用同一 AgentLoop；
- stdout/stderr、退出码和 schema v1 JSON；
- `/help`、`/exit` 和后续 Session/Memory 命令；
- wheel clean install 和 Windows UTF-8 输出。

## 4. 测试替身与夹具

- 脚本化 Provider：控制文本、Tool Call、Usage、错误和中断。
- 临时 Workspace：验证真实文件内容、Diff 和路径边界。
- 内存 Permission UI：控制允许、拒绝和暂停。
- 可故障 ToolExecutor：控制 timeout、started 后中断和输出截断。
- 可损坏 Session Store：验证尾部恢复、schema 和 uncertain 状态。

这些替身实现正式端口，不在产品运行时产生第二套控制流。

## 5. 核心 E2E 场景

1. 搜索符号、读取实现并回答。
2. 修改函数、确认 Diff、运行测试并报告证据。
3. 用户拒绝修改并继续给出反馈。
4. 文件在确认后发生变化，Edit 返回 stale snapshot。
5. 权限等待时退出，重启后恢复同一请求。
6. 工具 started 后进程中断，恢复为 uncertain。
7. 长会话触发 Context 管理并继续完成任务。
8. 新 Session 检索有效 Memory，来源变化后停止注入旧知识。

## 6. 关键不变量

- Provider 视图不以孤立 ToolResult 开头。
- 一个 Tool Call 最多有一个最终 ToolResult。
- 未授权副作用不会执行。
- Workspace 外路径不会进入文件系统操作。
- standard 模式的 Shell 不绕过 ASK。
- 压缩不修改 Session 原始事实。
- completed 和 uncertain 副作用都不会自动重放。
- Memory 不提高权限，也不代替 Session 恢复。
- Secret 不出现在配置展示、标准 Trace 和 Session export。

## 7. 真实模型评测

真实模型评测不进入核心 CI。使用固定小型任务集记录：

- 任务成功率；
- 平均模型调用和工具调用次数；
- Tool 参数或执行失败率；
- Token、耗时和权限请求；
- 未结算工具数量；
- 验证通过率。

评测报告必须记录 Provider、模型、配置、代码 commit、任务集和失败分类。

## 8. CI 门禁

```text
uv sync --locked
ruff check
basedpyright
pytest tests/unit
pytest tests/contract
pytest tests/integration
pytest tests/e2e
uv build
isolated wheel install
agent --help
docs link and import-boundary checks
```

目录尚未拆分完成时，CI 可以先运行 `pytest` 全集；M3 Closeout 前完成分层命令。

## 9. 完成定义

一个功能只有同时满足以下条件才完成：

- 用户可观察行为存在；
- 正常路径通过；
- 至少一个相邻失败路径通过；
- 暂停、取消、错误和恢复语义已定义；
- 对应 CLI 或 API 入口经过 Integration/E2E；
- 文档链接到真实代码和测试入口；
- 没有新增第二套循环或状态真相。
