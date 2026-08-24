# 版本路线图

路线图按“可观察能力”推进，不按目录或模块数量推进。每个里程碑都必须具备文档、测试和可演示场景。

## M0：设计基线

目标：冻结首轮产品边界和核心不变量。

交付：

- 产品章程、功能范围、架构、技术栈和运行时规范。
- Session/Context/Memory 分离设计。
- 工具与权限安全规范。
- 测试策略、ADR 和开放问题。

退出标准：所有 P0 能力都有明确所属版本和验收方式；不存在第二 Agent Loop 或第二 Session 真相。

## M1：最小模型调用与 CLI，v0.0.1

目标：一条命令完成一次可测试模型调用。

交付：

- `uv` 项目骨架、配置和 `agent -p`。
- Provider-neutral 类型。
- OpenAI-compatible Provider 和 Fake Provider。
- 文本流式 UiEvent、Usage、分类错误和 `--json` 结果契约。

演示：`agent -p "用一句话概括当前目录"` 返回模型文本；Fake 测试无需网络。

## M2：只读工具循环，v0.0.2

目标：模型能够通过工具理解仓库。

交付：

- 唯一 RuntimeRunner。
- `Read`、`Glob`、`Grep`。
- Tool Registry、参数校验和结果预算。
- 模型调用次数、工具轮次、超时和取消限制。

演示：模型搜索一个符号，读取实现并基于证据回答。

## M3：安全修改与权限，v0.0.3

目标：完成一次受控代码修改。

交付：

- Workspace root confinement。
- `Edit` 快照、Diff、权限确认和原子写入。
- `Shell` 工具、Windows `PowerShellExecutor`、超时、输出预算和逐次权限确认。
- plan/standard/bypass 模式。

演示：修改一个文件、展示 Diff、运行测试；并演示 stale snapshot 被阻止。

## M4：Session 与恢复，v0.0.4

目标：进程退出后可解释地继续任务。

交付：

- Append-only JSONL Event Log。
- 通过有界 JSONL 目录扫描实现 Session list/resume/status，不引入 SQLite。
- SessionEvent/UiEvent 到 Transcript 和 CLI 的统一投影。
- “暂停即 return、恢复即重放”的权限恢复、Ctrl-C 和 uncertain tool recovery。

演示：在权限确认前退出，重新启动后恢复同一请求；模拟工具启动后崩溃并拒绝自动重放。

## M5：Context 工程，v0.0.5

目标：长会话在有限上下文中保持合法和可恢复。

交付：

- Token 预算和高低水位。
- `ModelProfile`、`TokenEstimator`、Usage 误差记录和未知 tokenizer 安全余量。
- L0/L1 确定性压缩。
- L2 Artifact 外置与取回。
- L3 结构化 Checkpoint。
- prompt-too-long 一次恢复。

演示：构造超长工具输出，模型视图缩小，原始输出仍可取回，工具消息顺序合法。

## M6：Todo、完成门禁与记忆，v0.0.6

目标：清晰地区分“模型回答”和“任务完成”。

交付：

- `TodoWrite` revision 与四状态模型。
- CompletionGate 的未结项/未验证反馈、两轮有界补救和验证证据。
- `/remember`、Memory Candidate、作用域检索。
- SQLite Memory 元数据与不依赖中文 FTS 的有界检索。
- 根目录 `AGENTS.md` 与 Skills 渐进加载。

演示：修改任务未运行验证时先被 CompletionGate 要求补验，验证客观不可用时才标记 unverified；已验证的项目命令可以在后续 Session 中按来源检索。

## M7：完整终端体验，v0.1.0

目标：达到 README 承诺的稳定教学版本。

交付：

- Textual TUI 或最终确认的 Rich 交互界面。
- 会话选择、模型选择、工具活动、Diff 和权限卡片。
- OpenAI Responses 与 Anthropic Provider 至少完成一个。
- POSIX ShellAdapter 作为 P1 能力单独验收；若未完成，v0.1.0 继续明确标注 Windows-only。
- 端到端场景测试、安装测试和演示录屏。
- 架构阅读指南和一次完整 Turn Trace。

发布标准：全新环境可安装；无真实 Key 的测试全通过；三个代表任务可重复演示；文档与代码入口一致。

## M8：可选扩展，v0.2.x

候选：

- MCP stdio 客户端；
- 图片输入；
- 只读工具并发；
- 后台 Shell；
- 会话重放器；
- 小型公开评测结果。

M8 功能逐项进入，不作为 v0.1.0 发布阻塞项。

## 开发节奏规则

每个里程碑采用相同顺序：

```text
行为场景
  -> 协议与失败语义
  -> 最小实现
  -> Fake/单元测试
  -> 集成测试
  -> 故障注入
  -> 文档和演示
```

不得先搭建空的“大而全架构”，也不得在当前里程碑未验收时提前引入 MCP 或多 Agent。
