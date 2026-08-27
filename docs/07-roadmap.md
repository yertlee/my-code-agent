# Kernel-first 版本路线图

每个里程碑只增加一个可演示能力，并满足 `docs/10-development-governance.md` 的硬预算。

## 已完成：Agent Kernel 与 Coding preset

### M1：Provider Loop，v0.0.1

用户故事：一条 CLI 命令经过 Provider-neutral contract 获得流式回答。

交付：CLI、ChatProvider、Fake/OpenAI-compatible adapters、TurnResult 和错误分类。

### M2：Tool Loop，v0.0.2

用户故事：模型通过 Read/Glob/Grep 理解本地仓库并继续回答。

交付：唯一 Loop、Tool contract/registry、Workspace、工具轮次与调用限制。

### M3：Application Kernel，v0.0.3

用户故事：one-shot 与 interactive CLI 使用同一个 Application 和 AgentLoop 完成多 Turn 对话。

交付：AgentLoop、composition root、ContextBuilder/SessionStore contracts、RuntimeEvent 和 CLI。

### M4：可控编码 preset，v0.0.4

用户故事：Agent 展示 Diff，经用户允许后修改文件并运行 PowerShell 验证。

交付：Edit、Shell、TodoWrite、PermissionManager、prepared execution 与 stale snapshot。

### Kernel Baseline Closeout

目标：冻结 Kernel spine、移除无调用路径的预置抽象、建立自动复杂度门禁，并确认后续能力都通过
contracts/presets 接入。

### M5：Durable Session extension，v0.0.5

唯一故事：进程退出后，从 JSONL 重建 Session 并继续一次权限等待，不重复结果未知的副作用。

交付：5 类 append-only SessionEvent、唯一 reducer、JSONL list/status、permission claim、confirmation
校验和一个 resume 入口。

## 后续扩展

### M6：Context strategy extension，v0.0.6

唯一故事：长工具结果或长会话超过预算时，ContextBuilder 生成合法、可解释的压缩模型视图。

进入前冻结 TokenEstimator、预算和一个渐进压缩策略；原始 Session 事实保持不变。

状态：已完成。默认 deterministic 策略已覆盖 L1 工具输出压缩、L2 完整回合淘汰、L3 超限停止，
并通过 CLI/JSON 暴露投影摘要。

### M7：Memory extension，v0.0.7

唯一故事：Agent 在项目级 JSONL 账本保存带来源事实，并在新进程、新 Session 中召回、查看和删除。

交付顺序：冻结 MemoryService 与内部 Ledger/Writer/Retriever 契约；实现默认项目事实主线；完成
Context 低权限注入、CLI 观察和跨会话验收。替代写入、检索与 Context 策略在默认主线可用后接入。

状态：已完成。默认主线使用 append-only JSONL Ledger、证据驱动 Writer 与可解释关键词 Retriever；
one-shot、interactive 和 JSON CLI 均可观察和管理项目记忆。

### M8：Preset 与 Plugin release，v0.1.0

唯一故事：第三方包提供一个 Tool plugin，用户通过 preset 启用它，AgentLoop 无需修改。

交付：首批 contract 冻结、轻量 package discovery、一个外部插件示例、代码阅读路线和三个固定演示。

## 里程碑节奏

```text
一个用户故事
  -> 复用现有最小实现
  -> 确认 Kernel seam
  -> 预算检查
  -> 纵向实现
  -> 主路径 + 关键失败测试
  -> 可读性复查
  -> Closeout
```
