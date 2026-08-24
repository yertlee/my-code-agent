# M2 Closeout

状态：本地验收完成，等待 GitHub CI。

## 实际交付

- Provider-neutral `ToolDefinition`、`ToolCall`、`ToolResult`、reasoning stream 和工具消息。
- 唯一 RuntimeRunner，负责模型请求、串行工具执行、消息配对、Usage 汇总和终态。
- 固定 Workspace 根目录以及 `Read`、`Glob`、`Grep` 三个只读工具。
- 参数拒绝、输出截断、默认排除目录和路径逃逸防护。
- Fake 只读场景、OpenAI-compatible 流式 tool-call 拼接和 DeepSeek reasoning 回放。
- CLI `--cwd`、运行限制、工具活动、JSON 轮次统计和确定性演示。

## 验证事实

- 21 个无网络测试：17 个 unit、4 个 integration。
- Ruff 与 basedpyright 零问题。
- Fake 演示实际完成 3 次模型调用、2 次工具轮次和 `Grep → Read`。
- wheel/sdist 构建及隔离环境 console script 验收通过。
- 当前开发环境未提供 DeepSeek Key，因此没有把真实 M2 tool-call smoke 冒充为已验证。

## 偏差与遗留风险

- M2 不新增 durable SessionEvent；transcript 仍只在单次进程内存中，符合范围。
- `app.run_prompt` 为 M1 测试兼容入口，但内部只委托 RuntimeRunner，没有第二循环。
- OpenAI-compatible 服务在流式 tool-call 字段细节上可能存在方言差异；Fake/SDK 边界测试不能
  替代用户使用目标 DeepSeek 模型的人工 smoke。
- M2 的 Workspace confinement 不是 OS 沙箱；真正的写入与 Shell 权限边界在 M3 落地。

## 复杂度快照

- 主体 Python：19 个文件，约 1,158 行。
- 最大模块：RuntimeRunner 189 行；未触发 800 行复查线。
- durable SessionEvent：0；stream event：3；P0 Tool：3。
- 直接运行时依赖：2（OpenAI SDK、Pydantic）。

## M3 输入

- 先冻结 `Edit` snapshot/Diff/stale-write 和权限拒绝场景，再实现写入。
- 保持所有文件访问经过 Workspace，并复用现有 Tool Registry 与唯一 RuntimeRunner。
- PowerShell 风险策略遵循 ADR-010：standard 模式每次确认，不在 M3 临时发明脆弱的
  “安全命令”关键词分类器。
