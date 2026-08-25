# M3 行为场景

## S1：one-shot 保持兼容

给定一个 Provider 和 Workspace，执行 `agent -p "hello"` 后流式展示回答并以退出码 0 结束；
`--json` 仍只输出一个 schema v1 JSON 文档。

## S2：交互式连续对话

运行 `agent` 后输入两个普通任务。第二次 Provider 请求包含同一 Session 中第一次的用户消息、
assistant 回答及工具结果；输入 `/exit` 后正常关闭 Provider 并退出。

## S3：斜杠命令

- `/help` 展示可用命令，不调用模型。
- 空输入不调用模型。
- 未知 `/command` 返回可读提示，不调用模型。
- `/exit` 或 `/quit` 结束交互会话。

## S4：结构化活动

一次 `Grep → Read → final` 任务依次产生 turn started、tool started、tool completed、text delta 和
turn finished 活动。展示层只消费活动，不读取 AgentLoop 私有状态。

## S5：取消与超时

- AgentLoop 收到外部 task cancellation 后返回 `cancelled` 终态。
- 超过 Turn timeout 后返回 `turn_timeout`。
- Provider 在 Application 关闭时恰好关闭一次。

## S6：权限策略参与工具执行

Read、Glob、Grep 由 ReadOnlyPermissionPolicy 判定为 allow 后执行；未知或非只读工具不能绕过
policy 直接执行。

## S7：错误路径

- Provider stream 缺少 completed 事件时返回稳定失败终态。
- Provider 错误保留分类与 retryable。
- CLI 配置错误保持退出码 2 和 JSON 错误契约。
