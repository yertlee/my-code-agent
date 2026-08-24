# 架构决策记录

状态：`accepted`、`proposed`、`rejected`、`open`。

## ADR-001：产品定位为可讲解的真实 Coding Agent

- 状态：accepted
- 决定：实现 FirstCoder 类能力面，但不追求长期日用产品的完整功能。
- 原因：保证项目同时具有工程真实性和端到端可读性。

## ADR-002：只有一个正式 Agent Loop

- 状态：accepted
- 决定：所有交互、one-shot 和恢复路径共享 RuntimeRunner。
- 原因：避免控制流漂移和第二套停止/恢复语义。

## ADR-003：不以 Agent Framework 承担核心循环

- 状态：accepted
- 决定：自己实现模型—工具循环；Pydantic 仅用于边界校验。
- 原因：循环、暂停、恢复和压缩是项目的主要教学内容。

## ADR-004：Session Event Log 是持久化事实真相

- 状态：accepted
- 决定：JSONL 只追加事件为事实；P0 Session 列表扫描 JSONL，SQLite 到 M6 才作为可重建 Memory/查询索引。
- 原因：支持审计、教学、重放和崩溃恢复。

## ADR-005：Session、Context、Memory 分离

- 状态：accepted
- 决定：Context 和 Memory 都不能修改或替代 Session 事实。
- 原因：解决多份状态冲突和压缩破坏恢复的问题。

## ADR-006：Edit 是唯一文件修改工具

- 状态：accepted
- 决定：创建、替换、Patch 和删除都经 Edit、Diff、权限和快照检查。
- 原因：收敛副作用入口，减少权限和恢复组合。

## ADR-007：P0 工具串行执行

- 状态：accepted
- 决定：首版不并行执行工具；P2 仅允许显式安全的只读工具并发。
- 原因：先保证事件顺序和副作用语义可解释。

## ADR-008：长期记忆默认需要显式确认

- 状态：accepted
- 决定：模型只能生成 Candidate，不能把最终回答直接保存为事实。
- 原因：降低长期记忆污染和陈旧知识风险。

## ADR-009：首个 Provider 为 OpenAI-compatible

- 状态：proposed
- 决定：先实现 Chat Completions 兼容协议，再实现 OpenAI Responses 和 Anthropic。
- 原因：首版协议更简单，并兼容常见代理和本地服务。
- 风险：现代 OpenAI 特性需要第二个适配器才能完整展示。
- 未决：M1 使用哪个真实 endpoint/模型做人工 smoke test；Fake Provider 不受该选择阻塞。

## ADR-010：P0 使用 prompt-toolkit + Rich，P1 引入 Textual

- 状态：accepted
- 决定：先验证核心运行时，再增加完整 TUI。
- 原因：避免 UI 调试阻塞 Agent Loop 和恢复语义。

## ADR-011：跨平台 Shell 范围

- 状态：accepted
- 决定：P0 只保证 Windows 10/11 与 PowerShell；保留窄 ShellAdapter，POSIX 作为 P1 独立验收项。
- 原因：当前开发与演示平台是 Windows，同时实现两套路径、进程和取消语义会让 M3/M4 成本失控。

## ADR-012：项目名称、包名和 CLI 命令

- 状态：open
- 当前占位：目录 `coding-agent`、包 `coding_agent`、命令 `agent`。
- 要求：M1 closeout 前确定；骨架阶段沿用占位，迁移成本仍很低。

## ADR-013：许可证

- 状态：open
- 建议：MIT。
- 影响：首次公开发布和参考项目代码边界；不阻塞从零编写的 M1 核心代码。

## ADR-014：Token 计数采用分层估算

- 状态：accepted
- 决定：ContextEngine 注入 TokenEstimator；优先 Provider 计数能力，其次已知 encoding 的 tiktoken，未知模型使用带 25% 默认安全余量的保守 UTF-8 估算，并用返回 Usage 校准误差。
- 原因：兼容服务 tokenizer 不统一；Usage 发生在请求之后，无法独立承担请求前预算。

## ADR-015：P0 Shell 不做安全自动分类

- 状态：accepted
- 决定：模型可见工具名统一为 `Shell`；P0 后端为 PowerShellExecutor。standard 模式中每次调用都 ASK 且只允许一次；静态 CommandInspection 仅用于解释，不作为自动放行依据。
- 原因：PowerShell 的管道、变量、子表达式和间接执行使关键词分类器无法兑现可靠安全承诺。

## ADR-016：权限暂停通过 return + replay 恢复

- 状态：accepted
- 决定：Runner 记录 pending request 后返回调用方，不跨用户等待保留可变调用栈；resume 从 SessionView 重建。
- 原因：让进程内等待与进程退出后的恢复共享唯一语义。

## ADR-017：P0 只自动加载根目录 AGENTS.md

- 状态：accepted
- 决定：仅根目录 `AGENTS.md` 进入低权限项目指导区，显示路径和哈希并允许禁用；不递归、不自动兼容其他文件名。
- 原因：收窄攻击者可控 instruction 入口，并保持项目规则来源可观察。

## ADR-018：Durable 事件注册表保持最小

- 状态：accepted
- 决定：P0 使用 11 种 durable SessionEvent；工具阶段和终态放 payload 枚举；流式文本等使用不持久化 UiEvent。
- 原因：恢复只需要稳定事实，不需要把每个 UI 状态都升级为领域事件。

## 决策维护规则

- 已接受决策发生变化时新增 ADR，不悄悄改写历史理由。
- 文档正文只描述当前有效方案；本文件保留决策演进。
- 每个重大 PR 必须说明是否违反现有 ADR。
- 如果一个实现需要第二循环、第二事实真相或绕过权限，应先修改 ADR，再写代码。
