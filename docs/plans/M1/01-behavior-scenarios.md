# M1 行为场景

## S1：Fake Provider 普通输出

给定未配置真实 API，用户执行：

```powershell
agent -p "用一句话概括当前目录"
```

CLI 使用 Fake Provider，逐段输出固定文本并以退出码 0 结束。

## S2：机器可读输出

用户增加 `--json` 后，stdout 只有一个 JSON 对象；流式 delta 不直接打印，诊断只允许写
stderr。结果包含 schema、turn 标识、状态、完整文本、Usage 和错误字段。

## S3：真实兼容服务

用户显式选择 `--provider openai-compatible`，并配置 model、API Key 环境变量和可选
base URL。Provider 发送 Chat Completions 流式请求，将供应商对象转换为内部事件。

## S4：配置失败

真实 Provider 缺少 model 或 API Key 时不发送网络请求，返回配置错误和退出码 2；错误消息
不能包含 Secret。

## S5：Provider 失败

认证、限流、超时、网络、上下文过长和服务端错误转换为内部错误类型。CLI 返回退出码 1，
`--json` 仍维持同一结果 schema。
