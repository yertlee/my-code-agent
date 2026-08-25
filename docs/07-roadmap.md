# 版本路线图

路线图按可运行的纵向能力推进。每个里程碑同时交付源码、测试、CLI 场景、阅读入口和
Closeout。

## M0：设计基线

目标：冻结产品边界、核心模块和状态不变量。

交付：产品章程、架构、技术栈、Runtime、Session/Context/Memory、权限、测试、ADR 与治理。

## M1：最小模型调用，v0.0.1

目标：通过一条 CLI 命令完成可测试的流式模型调用。

交付：

- Python/uv 项目与 console script；
- Provider-neutral 类型；
- OpenAI-compatible Provider；
- 文本流式输出、Usage、错误分类和 JSON 结果。

状态：已完成。

## M2：只读工具循环，v0.0.2

目标：模型通过工具理解本地仓库。

交付：

- 唯一 RuntimeRunner；
- Read、Glob、Grep；
- Workspace 与 Tool Registry；
- 流式 Tool Call、调用次数、工具轮次、超时和取消。

状态：已完成。

## M3：架构骨架与交互式 CLI，v0.0.3

目标：形成完整 Agent 的可执行包边界，并让交互式和 one-shot 共用同一 AgentLoop。

交付：

- app/agent/runtime/session/context/memory/permissions 包边界；
- RuntimeRunner 收敛为 `agent/AgentLoop`；
- cancellation、user input 和 RuntimeEvent；
- composition root 与 SessionBootstrap；
- InMemorySessionStore、基础 ContextBuilder、ReadOnlyPermissionPolicy 和 EmptyMemoryRetriever；
- Rich/prompt-toolkit 交互式 CLI、`/help` 和 `/exit`；
- 现有读取仓库纵向场景通过新装配路径运行。

退出标准：核心包都进入真实调用链；不存在第二循环；M1/M2 行为保持兼容。

状态：已完成。

## M4：写工具与权限，v0.0.4

目标：完成一次可审查、可拒绝的代码修改与验证。

交付：

- Edit、Shell、TodoWrite；
- Permission policy、manager 和 grants；
- Diff、snapshot recheck 和 atomic replace；
- PowerShell timeout、输出预算和进程终止；
- plan、standard、bypass 模式。

退出标准：CLI 可以修改文件、展示并确认 Diff、运行测试，并阻止 stale write。

状态：已完成。

## M5：Session 与恢复，v0.0.5

目标：进程退出后从本地事实继续任务。

交付：

- JSONL event、writer、store、reducer 和 SessionView；
- Session list/resume/status；
- 权限等待恢复；
- Ctrl-C 与 uncertain tool settlement；
- create/resume 共用的装配路径。

退出标准：权限等待和工具 started 两处中断后，重启进程得到正确状态且不重复副作用。

## M6：Context 工程，v0.0.6

目标：长会话在模型预算内保持消息合法、事实可恢复。

进入条件：先完成 Context 详细设计评审，冻结 Token 估算、预算、压缩和恢复协议。

交付：

- 模型上下文预算与消息合法投影；
- 长工具结果管理；
- 渐进压缩与会话摘要；
- prompt-too-long 有界恢复；
- CLI 预算和压缩活动展示。

退出标准：压缩后请求合法且低于目标预算，原始 Session 事实仍可审计和取回。

## M7：Memory 与完成判断，v0.0.7

目标：跨 Session 复用可信知识，并区分模型回答和任务完成。

进入条件：先完成 Memory 详细设计评审，冻结类型、状态、存储、检索和失效协议。

交付：

- Todo 状态机与 CompletionGate；
- Memory 创建、用户控制、作用域检索、来源校验和过期处理；
- Memory 查看、保存、刷新和删除命令；
- 根目录 AGENTS.md 与 Skills 渐进加载。

退出标准：新 Session 能取回有效知识；来源变化后旧知识不再作为有效事实注入。

## M8：可阅读版本发布，v0.1.0

目标：形成可安装、可运行、可学习和可展示的稳定 CLI Agent。

交付：

- CLI、配置、错误信息和安装流程收口；
- 真实 OpenAI-compatible Provider 场景；
- 完整架构文档、代码阅读路线和一轮 Turn Trace；
- 理解仓库、修改并验证、恢复长会话并使用 Memory 三个固定演示；
- 源码规模、依赖边界、测试和文档发布报告。

Textual TUI、MCP、多模态、POSIX、并发工具和后台进程进入 v0.1.0 之后的独立路线图。

## 开发顺序

```text
用户可观察行为
  -> 现有实现与接口审阅
  -> 状态归属和失败语义
  -> 最小纵向实现
  -> Unit / Contract
  -> Integration / E2E
  -> CLI 演示
  -> 阅读指南与 Closeout
```
