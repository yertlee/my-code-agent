# 功能范围与能力清单

## 1. 核心能力 P0

P0 定义首个可讲解、可运行版本必须具备的能力。

### CLI 与工作区

- `agent`：启动交互模式。
- `agent -p "任务"`：执行一次任务并退出。
- `agent --cwd <path>`：指定项目根目录。
- `agent -p "任务" --json`：stdout 只输出一个版本化 JSON 结果，进度和诊断写入 stderr。
- P0 只自动读取仓库根目录的 `AGENTS.md`，并显示已加载文件及内容哈希；支持显式关闭。
- 配置优先级：CLI > 项目配置 > 用户全局配置 > 内置默认值。
- P0 只保证 Windows 10/11 与 PowerShell；POSIX 兼容不作为首版验收条件。

### 模型与流式输出

- 一个 OpenAI-compatible Provider。
- Provider-neutral 的请求、响应、工具调用、Usage 和错误类型。
- 文本流式输出。
- 流式工具参数必须累积完整并验证后才能执行。
- 认证、限流、超时、网络错误和上下文过长需分类。

### 工具

- `Read`：按行读取文本文件。
- `Glob`：按模式发现文件。
- `Grep`：搜索文件内容。
- `Edit`：唯一文件修改入口。
- `Shell`：执行有时间限制的项目命令；P0 后端是 PowerShell。
- `TodoWrite`：维护当前任务的轻量计划。

### 权限

- 只读工具默认允许。
- 文件修改展示可信 Diff。
- 文件修改按风险请求确认；P0 的每次 Shell 调用都请求确认。
- 文件修改支持本次允许、本会话允许和拒绝；Shell 仅支持逐次允许或拒绝。
- 权限决定由程序执行，不由 Prompt 执行。

### Session 与恢复

- 创建、列出和恢复 Session。
- Append-only JSONL 事实日志。
- 记录用户消息、模型消息、工具生命周期、权限决定、压缩检查点和终态。
- 发现未完成副作用时标记 `uncertain`，不自动重放。
- Ctrl-C 触发协作式取消并写入可恢复终态。

### Context

- 基于模型窗口和输出预留计算输入预算。
- 保持 assistant tool call 与 tool result 成对。
- 超长工具输出移入 Artifact，并保留可恢复引用。
- 自动压缩、手动压缩和 prompt-too-long 恢复。
- 压缩只改变模型视图，不删除事实日志。

### 完成判断

- 无未结算工具调用。
- 无等待中的权限请求。
- Todo 的 `pending`/`in_progress` 项会阻止“已完成”终态，除非用户明确取消或将其标为 blocked。
- 最近一次文件修改之后没有验证证据时，CompletionGate 至少反馈一次并要求模型验证。
- 未验证只能在用户明确要求跳过、验证客观不可用或有界补救次数耗尽后结束，并使用 `completed_unverified` 终态说明缺失证据。
- 命中轮次、时间、模型调用预算时返回具体停止原因。

## 2. 增强能力 P1

- Textual TUI：活动流、工具卡片、Diff、权限面板和状态栏。
- OpenAI Responses Provider。
- Anthropic Messages Provider。
- Skills 发现、目录摘要和按需加载。
- 显式 `/remember` 与记忆候选审核。
- 多级上下文压缩和结构化任务交接摘要。
- 会话 Fork、导出和调试 Trace。
- 小型 Coding Task 评测集。
- POSIX ShellAdapter 与跨平台进程树终止测试。
- 额外项目规则文件名，但必须由用户显式配置启用。

## 2.1 `--json` P0 输出契约

```json
{
  "schema_version": 1,
  "session_id": "ses_...",
  "turn_id": "turn_...",
  "status": "completed",
  "stop_reason": "completed",
  "output_text": "...",
  "verified": true,
  "verification": [{"command": "pytest", "exit_code": 0}],
  "tools_used": ["Read", "Shell"],
  "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
  "error": null
}
```

- `status` 可取 `completed`、`completed_unverified`、`waiting_for_permission`、`limited`、`cancelled`、`failed`。
- `verified` 为 `true`、`false` 或不适用时的 `null`；不得仅根据模型自述置为 `true`。
- 退出码：成功验证为 `0`，CLI/配置错误为 `2`，完成但未验证为 `3`，等待权限/受限/取消为 `4`，运行时或 Provider 失败为 `1`。
- `--json` 被定义为非交互 one-shot：遇到权限 ASK 时不读取 stdin，返回 `waiting_for_permission`，可由后续 resume 命令继续；普通 `-p` 仍可显示交互确认。

## 3. 展示性扩展 P2

- MCP stdio 客户端和显式启用的服务器配置。
- 图片与小型文本附件。
- 只读工具安全并发。
- 后台 Shell 任务的启动、轮询和中断。
- HTML 或 TUI 形式的会话重放器。

## 4. 暂不实现

- 多 Agent 团队和异步任务 DAG。
- 自动网页搜索、浏览器操作和外部账号连接。
- IDE 插件、Web Dashboard 和远程执行。
- 自动写入的无审核长期记忆。
- 通用向量数据库、知识图谱和复杂 RAG Pipeline。
- 自动生成或修改 Agent 自身代码、Prompt 或 Skills。

## 5. 功能进入规则

每项功能进入路线图前必须提供：

1. 可观察的用户行为。
2. 所属模块和依赖方向。
3. 新增的持久化事实或明确声明无持久化。
4. 至少一个失败场景。
5. 自动化验收测试。
6. 对源码规模和讲解复杂度的影响。
