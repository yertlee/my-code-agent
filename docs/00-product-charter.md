# 产品章程

## 1. 产品定义

本项目是一个面向学习、讲解、扩展和作品展示的本地 CLI Coding Agent。

一句话定义：

> 用一个可通读的 Agent Kernel 驱动真实编码任务，以完整可用的默认实现承载主线，再通过窄策略
> 接缝对照 Context 与 Memory 的不同工程方案。

读者应能从一次 CLI 输入出发，沿源码解释模型请求、Agent Loop、工具执行、权限暂停和最终输出；
也应能在不修改 AgentLoop 的情况下增加一个 Tool 或 Provider。

## 2. 产品结构

产品按两层建设：

```text
Agent Kernel
  = Provider-neutral protocol
  + one AgentLoop
  + Tool registry
  + runtime limits/events
  + Application composition

Capability Extensions
  = Provider adapters
  + coding tools
  + permission policy
  + Session implementation
  + Context strategy
  + Memory implementation
  + CLI presentation
```

Kernel 保持稳定、短小；首个稳定版本先交付一套完整可用的默认 Coding preset。Context 与 Memory
在默认实现验证契约后允许替换策略。首版使用 Python Protocol、Registry 和显式装配，不引入独立
插件运行时或组合矩阵。

## 3. 核心用户故事

用户进入代码仓库，通过 CLI 要求 Agent 修复一个小型缺陷：

1. Provider 接收由 ContextBuilder 构造的请求。
2. AgentLoop 在模型响应与 Tool Call 之间循环。
3. ToolRegistry 校验并执行读取、编辑或命令工具。
4. PermissionManager 在副作用前暂停并取得用户决定。
5. 工具结果回到同一 Loop，模型给出最终回答。
6. SessionBackend 支持跨进程恢复，Context 在预算内生成模型视图，Memory 为新 Session 召回带来源
   的项目事实。

所有里程碑都必须增强这条主线或提供一个可独立挂载的能力。

## 4. 成功标准

### 可读性

- 新读者能在 30 分钟内沿不超过 8 个核心文件讲完一次 Turn。
- AgentLoop 保持单一实现，源码不超过 500 行。
- 单个普通模块不超过 300 行；Provider adapter 目标不超过 250 行，AgentLoop 适用独立上限。
- v0.1.0 全部产品 Python 源码不超过 8,000 行；达到 6,000 行时必须进行范围复查。
- Agent Kernel 指定目录总计不超过 2,000 行，统计范围写入开发治理文档。

### 可扩展性

- 新 Tool 只需实现 Tool contract 并在 composition root/preset 注册。
- 新 Provider 只需实现 ChatProvider，不修改 AgentLoop。
- SessionBackend、ContextBuilder、PermissionPolicy 和 EventSink 可由装配层替换。
- AgentLoop 只依赖顶层 MemoryService；Writer、Retriever 和 Ledger 保持在 memory 包内部。
- 默认 Context 策略与默认 Memory 服务必须先完成真实调用路径，替代策略随后按独立里程碑接入。
- 扩展模块依赖公开 contract，不依赖 AgentLoop 的私有状态。

### 可运行性

- CLI one-shot 与 interactive 共用同一 Application 和 AgentLoop。
- 文件副作用经过 Workspace、Diff、权限和 stale snapshot 检查。
- 每个循环都有模型调用、工具轮次、总时间和取消边界。
- CI 不依赖真实 API Key 或公网；发布前执行真实 Provider smoke test。

## 5. 功能准入

功能进入当前里程碑必须同时满足：

1. 服务本里程碑唯一演示，或保护该演示已经存在的副作用安全边界；
2. 在本里程碑结束时存在真实调用路径；
3. 已选择能够完成用户行为的最小实现；
4. 符合源码、模块、概念和文档预算；
5. 能用一个正常场景和一个关键失败场景验收。

Kernel 公开 seam 可以只有一个默认实现，但必须被真实装配路径使用。未来能力不得通过空实现、预留
事件、未使用配置或兼容门面提前进入产品源码。

## 6. 产品边界

- Local-first、single-agent-first、CLI-first。
- 核心循环由项目源码实现，Provider SDK 只存在于 adapter。
- v0.1.0 聚焦单机代码仓库、串行工具和一个正式 Coding preset。
- 团队控制台、IDE 集成、云同步、多 Agent DAG 和 OS 级沙箱属于独立产品阶段。
