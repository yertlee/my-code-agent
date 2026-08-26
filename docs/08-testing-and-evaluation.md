# 测试与可读性验证

## 1. 测试目标

测试证明 Kernel contracts、Coding preset 主路径和关键副作用边界。测试数量不是项目卖点；每个测试
都应对应用户行为、公开 contract、已发生缺陷或明确安全不变量。

## 2. 当前测试层级

| 层级 | 目标 | 示例 |
| --- | --- | --- |
| Unit | 单个 contract/能力实现 | Provider 流、Workspace、Tool、Permission |
| Integration | Kernel 与扩展协作 | AgentLoop 工具循环、权限暂停、Application 多 Turn |
| CLI | 用户入口和退出契约 | one-shot、interactive、JSON、Diff/permission |
| Build smoke | 发布物可运行 | wheel、`agent --help`、`agent --version` |

Fake Provider 用于控制外部响应和故障；产品能力仍通过真实临时 Workspace、ToolResult、文件状态和
CLI 结果验证。

## 3. Kernel Contract tests

Kernel 必须持续证明：

- 自定义 ChatProvider 可以驱动 AgentLoop；
- 自定义 Tool 可以通过 ToolRegistry 注册和执行；
- 自定义 PermissionPolicy 可以改变 allow/ask/deny；
- SessionStore、ContextBuilder 和 EventSink 通过注入工作；
- one-shot 与 interactive 不建立第二个 Loop。

## 4. 每个能力的最小测试集

一个里程碑默认只要求：

1. 一个完整用户主路径；
2. 一个最重要的相邻失败或安全边界；
3. 受影响的既有主路径回归；
4. 一个无需网络的 CLI 演示。

新增更多矩阵前，必须说明它保护的真实合同。未来 Session、Context、Memory 的测试集在各自设计
评审时确定。

## 5. 当前关键不变量

- AgentLoop 只有一个具体实现。
- Provider adapter 类型不进入 protocol 或 Tool。
- 未授权 Edit/Shell 不执行。
- Workspace 外路径不进入文件系统操作。
- Edit 确认后文件变化会返回 stale snapshot。
- standard 模式 Shell 每次 ASK。
- Tool Call 与 ToolResult 保持配对。
- JSON stdout 只包含一个 TurnResult object。

## 6. 自动门禁

```powershell
uv run pytest
uv run ruff check .
uv run basedpyright
uv build
uv run agent --help
```

`tests/architecture/test_kernel_guardrails.py` 额外执行源码总量、AgentLoop 行数、运行依赖和 Kernel
导入方向检查。改变门禁常量需要在当前里程碑 Closeout 中说明并获得用户确认。

## 7. 完成定义

一个功能完成时必须同时具备：

- 用户可观察入口；
- Kernel seam 或现有能力归属；
- 主路径和关键失败测试；
- 无网络固定演示；
- 预算内实现；
- 文档链接到真实代码入口；
- 没有未使用的公开类型、配置和事件。
