# 技术栈

## 1. 当前运行栈

| 领域 | 选择 | 用途 |
| --- | --- | --- |
| 语言 | Python 3.12 | Kernel 与内置扩展 |
| 包管理 | uv | lock、开发环境、构建与运行 |
| 边界校验 | Pydantic | Tool schema 和外部协议校验 |
| Provider SDK | openai | OpenAI-compatible adapter |
| CLI | argparse + prompt-toolkit + Rich | one-shot、interactive 与展示 |
| 测试 | pytest + pytest-asyncio | Unit/Integration/CLI |
| 质量 | Ruff + basedpyright | 格式、静态检查和类型检查 |
| 构建 | setuptools | wheel 与 console script |

这些依赖都存在当前产品调用路径。新增 runtime dependency 必须说明它替代的自研代码、对 Kernel
可读性的影响，并通过 ADR 与用户审核。

## 2. Kernel 技术选择

- 核心循环直接使用 `asyncio`，不叠加 Agent framework。
- 可替换能力使用 Python Protocol。
- 多实现集合使用显式 Registry。
- 默认能力由 composition root 构造，不使用全局 service locator。
- 插件 package discovery 在 v0.1.0 收口里程碑实现；此前使用普通 Python 对象装配。

## 3. Provider 边界

`ChatProvider.stream(ModelRequest)` 是唯一模型调用 seam。Provider adapter 负责：

- SDK/HTTP 类型转换；
- 流式文本与 Tool Call 累积；
- Usage 和错误归类；
- Provider 特有字段回放。

AgentLoop、Tool 和 Session 不接触 SDK client 或 vendor response 类型。

## 4. 本地状态

v0.0.8 提供 `InMemorySessionStore` 与 `JsonlSessionStore`，都通过 `SessionBackend` contract 装配。
Session 列表直接扫描并重放事实文件；索引只有在出现可测量性能问题后进入独立扩展。

## 5. 平台范围

- 当前正式平台是 Windows 10/11。
- Shell plugin 使用 PowerShell，并负责 timeout 与进程树终止。
- Workspace 使用 `pathlib` 解析和限制路径。
- POSIX Shell 是后续独立 plugin，不在当前实现中预置分支。

## 6. Secret

- API Key 只从用户指定的环境变量读取。
- CLI 和配置错误只显示环境变量名，不显示值。
- Provider 配置不进入 Provider-neutral DTO。
- Context 扩展开始前冻结 TokenEstimator、预算和渐进压缩策略。
