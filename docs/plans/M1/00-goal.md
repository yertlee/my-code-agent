# M1 目标：最小模型调用与 CLI

## 用户可观察结果

用户执行 `agent -p "任务"` 后，可以看到一次流式模型文本；执行同一命令并增加
`--json` 时，stdout 只包含一个符合 schema v1 的 JSON 对象。

M1 同时提供无需 API Key 的 Fake Provider，以及可配置 `base_url` 的
OpenAI-compatible Chat Completions Provider。

## 本里程碑不做

- 工具调用与 RuntimeRunner 循环；
- Session JSONL、恢复、权限与 Workspace；
- Context 压缩、Todo 和 Memory；
- 交互式 REPL/TUI。

这些能力不能以空接口提前进入 M1。
