# M4 目标：写工具与权限

版本目标：v0.0.4。

M4 让 Agent 在固定 Workspace 内完成一次可预览、可拒绝、可验证的代码修改。文件写入和
PowerShell 命令必须经过程序权限策略；模型不能批准自己的工具调用。

## 用户可观察结果

- Agent 可以使用 `Edit` 创建、精确替换或删除 UTF-8 文件。
- 修改前展示可信 unified diff，用户可以拒绝、允许一次或对同一路径允许本 Session。
- 用户确认后文件发生变化时，Edit 返回 `stale_snapshot`，不覆盖新内容。
- Agent 可以请求 PowerShell 命令；standard 模式每次询问且只能允许一次或拒绝。
- plan 模式禁止副作用；bypass 模式允许副作用但仍展示活动和 Diff。
- TodoWrite 可以维护带 revision 的进程内任务快照。

## 非目标

- 跨进程权限恢复和 JSONL Session。
- 持久化 permission grant。
- POSIX Shell、后台进程和通用命令安全分类。
- CompletionGate 强制验证和 Todo 完成判断。
