# M1 设计

## 最小调用链

```text
argparse CLI
  -> AppConfig
  -> provider factory
  -> run_prompt
  -> ChatProvider.stream(ModelRequest)
  -> TextDelta* + ResponseCompleted
  -> TurnResult
  -> text or JSON presenter
```

M1 没有 Agent 工具循环。`run_prompt` 只消费一次 Provider stream，因此不会形成第二套
RuntimeRunner。M2 增加工具时，唯一循环进入 `runtime` 模块。

## 内部协议

- `ModelMessage`、`ModelRequest`：不包含 SDK 对象。
- `TextDelta`：临时展示事件。
- `ResponseCompleted`：Provider 终态、finish reason 和 Usage。
- `ProviderError`：带稳定 kind 和 retryable 字段。
- `TurnResult`：CLI 文本和 JSON 输出共享的唯一结果对象。

## Provider 边界

Fake Provider 与 OpenAI-compatible Provider 实现同一个 `ChatProvider` Protocol。真实适配器可以
依赖 OpenAI Python SDK，但 SDK 类型不得进入 protocol、app 或 CLI。

Chat Completions 的 `stream_options.include_usage` 并非所有兼容服务都支持，因此提供
`--no-stream-usage` 能力开关；关闭时 Usage 字段为 null，而不是伪造数字。

## 配置优先级

```text
CLI > environment > built-in defaults
```

M1 支持 `CODING_AGENT_PROVIDER`、`CODING_AGENT_MODEL`、`OPENAI_BASE_URL` 和由
`--api-key-env` 指定的 Secret 环境变量。Secret 不允许通过 CLI 参数直接传值。
