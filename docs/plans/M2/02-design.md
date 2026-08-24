# M2 设计

## 唯一调用链

```text
CLI
  -> RuntimeRunner
  -> ModelRequest(messages + tool definitions)
  -> ChatProvider stream
  -> complete ToolCall
  -> ToolRegistry validation
  -> ReadOnlyTool.execute(Workspace)
  -> ToolResult message
  -> RuntimeRunner next model request
```

`app.run_prompt` 只保留为 M1 兼容包装，内部转交 RuntimeRunner；不得实现第二个模型循环。

## 协议不变量

- Tool arguments 在流结束前只是字符串片段，禁止执行。
- assistant tool calls 必须先写入内存 transcript，再追加匹配的 tool results。
- ToolResult 即使失败也使用相同 `tool_call_id` 返回模型。
- 同一响应的多个工具 P0 串行执行。
- SDK 对象不得离开 Provider adapter。

## Workspace

根目录在启动时解析并固定。Read/Glob/Grep 共享同一 Workspace，默认排除 `.git`、`.venv`、
`.coding-agent`、build、dist 和缓存目录。

## 输出预算

单次工具结果默认最多 20,000 字符；Read 最多 400 行，Glob/Grep 最多 100 条。截断必须
显式标记，不能伪装成完整结果。

## Runtime 默认限制

- 8 次模型调用；
- 6 个工具轮次；
- 120 秒总时间；
- Provider 错误成为稳定失败终态；工具错误成为带原 `tool_call_id` 的普通 ToolResult，让模型
  有界修正。
