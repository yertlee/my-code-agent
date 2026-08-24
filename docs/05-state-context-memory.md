# Session、Context 与 Memory 设计

## 1. 三者不能混为一谈

| 系统 | 回答的问题 | 生命周期 | 是否是真相 |
| --- | --- | --- | --- |
| Session | 实际发生了什么？ | 一次或多次交互会话 | 是，append-only 事实 |
| Context | 下一次模型需要看到什么？ | 每次模型请求重新构造 | 否，是预算内投影 |
| Memory | 未来任务值得复用什么？ | 跨 Session | 否，是有来源的派生知识 |

核心原则：

> Session 不能靠 Memory 恢复，Memory 不能代替完整历史，Context 压缩不能删除 Session 事实。

## 2. Session 持久化

建议路径：

```text
<project>/.coding-agent/
  sessions/<session-id>.jsonl
  artifacts/<session-id>/...
  permissions.json
```

M4 的 Session list/resume/status 读取 JSONL 首尾事件并做有界目录扫描，不依赖数据库。`index.sqlite3` 到 M6 才随 Memory 引入，且始终是可重建派生索引。

每条 JSONL 事件至少包含：

```json
{
  "schema_version": 1,
  "event_id": "evt_...",
  "session_id": "ses_...",
  "turn_id": "turn_...",
  "sequence": 42,
  "timestamp": "...",
  "type": "tool_lifecycle",
  "payload": {"status": "completed"}
}
```

不变量：

- `sequence` 在一个 Session 内严格递增。
- Event ID 不重复。
- 事件追加后不原地修改。
- JSONL 最后一个不完整记录可以在启动时截断并报告。
- 未知未来 schema version 拒绝恢复，不能猜测迁移。

## 3. Session 重放与恢复

重放生成 `SessionView`：

- messages
- pending permission
- unsettled tool calls
- current todo plan
- latest context checkpoint
- accumulated usage
- terminal status

恢复规则：

- `tool_lifecycle(status=requested)` 但没有 `started`：可以重新请求授权，不自动执行。
- `tool_lifecycle(status=started)` 但没有终态：追加 `uncertain` 状态，尤其禁止自动重放写操作。
- 已完成工具只恢复结果，不重新执行。
- 已完成 Session 接受新用户消息时开启新 Turn。
- 派生索引丢失时从 JSONL 重建。

## 4. Context 构建

ContextEngine 的输入包括：

- SessionView；
- 当前 Provider 能力和上下文窗口；
- 系统规则、项目规则、Skills 目录摘要；
- Tool Definition；
- 输出 Token 预留；
- 当前任务计划和记忆注入。

ContextEngine 还接收 `ModelProfile` 和 `TokenEstimator`。Profile 至少声明上下文窗口、输出预留、估算器类型和安全余量；未知模型不得套用另一个模型的 tokenizer 后宣称精确。

预算公式初稿：

```text
input_capacity = context_window - output_reserve
safe_estimate = estimated_input_tokens + uncertainty_margin
high_watermark = input_capacity * configured_high_ratio
target_after_compaction = input_capacity * configured_target_ratio
```

默认可从 `configured_high_ratio=0.90`、`configured_target_ratio=0.72` 起步，但必须集中配置并通过场景测试校准。未知 tokenizer 的默认误差余量为估算值的 25%；Provider Usage 记录 estimate/actual 偏差，接近高水位时可调用 Provider 的输入计数能力。若 Provider 无计数能力，则保守压缩，并依靠一次 `prompt_too_long` 恢复兜底。

## 5. 压缩等级

### L0：合法投影

- 移除纯 UI 事件和不可见诊断。
- 验证工具调用与结果配对。
- 合并允许合并的相邻文本。

### L1：确定性裁剪

- 去除重复状态快照。
- 对旧的 Todo 快照只保留最新有效状态。
- 折叠无价值的重复错误和空输出。

### L2：工具结果外置

- 超长 Grep、Read、Shell 输出保存为 Artifact。
- 模型视图保留摘要、路径、字节数、哈希和检索方式。
- 原始输出仍可通过 `ReadArtifact` 或受控 Read 取回。

### L3：结构化 Checkpoint

对已经完成的旧任务段生成结构化交接：

- 用户目标；
- 已完成工作；
- 修改文件；
- 执行证据；
- 关键决定和约束；
- 未解决问题；
- 下一步。

Checkpoint 是新事件，不替换旧事件。

### L4：紧急模型压缩

只在确定性压缩不足或 Provider 返回 prompt-too-long 时调用模型生成候选摘要。候选需经过字段校验和 Token 节省检查才能提交。

## 6. 压缩不变量

- 不产生孤立 `tool` 消息。
- 不拆分一组 assistant tool calls 与匹配结果。
- 当前任务依赖的最新源码证据不能仅因篇幅大而被总结。
- Artifact 引用必须可恢复并限制在 Session 数据目录内。
- Checkpoint 必须记录所覆盖的事件范围和摘要来源。
- 压缩失败不能破坏上一个有效模型视图。

## 7. 长期 Memory

Memory 类型初稿：

- `user_preference`：用户明确表达的稳定偏好。
- `project_fact`：从仓库文件验证出的事实。
- `workflow`：已执行成功的构建、测试或发布方式。
- `decision`：架构选择、原因和替代方案。
- `lesson`：失败原因及可复现证据。

每条 Memory 至少包含：

- ID、类型和正文；
- workspace scope；
- 可选 branch/path scope；
- 来源 Session/Event/文件路径；
- 创建时间和最后验证时间；
- 状态：candidate/accepted/rejected/stale；
- 可选父 Memory ID；
- 可选过期策略。

## 8. Memory 写入策略

P1 采用两条路径：

1. 用户显式 `/remember`：直接创建 accepted memory，但仍记录来源。
2. 任务结束生成 candidate：只有用户确认或确定性规则验证后才接受。

禁止模型把自己的最终回答直接当作项目事实写入长期 Memory。

## 9. Memory 检索策略

第一版不使用 Embedding。按以下顺序检索：

1. workspace 精确匹配；
2. path/branch 作用域匹配；
3. 类型与标签；
4. 全文搜索；
5. 最近验证时间；
6. 有界数量与 Token 预算。

检索结果以“内容 + 来源 + 作用域 + 更新时间”注入，模型必须能区分事实、偏好和候选。

第一版全文搜索不依赖 SQLite FTS5 分词：对有界候选使用 Unicode casefold/substring，必要时用 `LIKE` 粗筛。中文分词、FTS/trigram 或 Embedding 只有在真实语料评测证明需要后再加入。

## 10. 项目规则与 project_fact 的分流

- P0 只自动读取仓库根目录的 `AGENTS.md`。它是每次请求重新读取的当前项目指导，不复制为长期 Memory 真相。
- `project_fact` 是带来源文件路径、内容哈希和最后验证时间的派生候选；源文件哈希变化时自动标记 stale。
- 当前仓库文件与 Memory 冲突时，重新读取的文件证据优先，Memory 不得覆盖项目规则或权限策略。
- 项目规则只能影响代码风格、构建方式和任务偏好，不能授予工具权限、扩大 workspace、泄露 Secret 或修改运行时安全限制。
