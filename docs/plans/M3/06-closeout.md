# M3 Closeout

状态：完成；本地验收通过。

## 实际交付

- `app/agent/runtime/session/context/memory/permissions` 七个正式边界。
- 唯一 AgentLoop，负责模型请求、工具串行执行、限制、错误、取消和 TurnResult。
- AgentApplication 持有当前 Session 和 Provider 生命周期，one-shot 与交互式入口共享装配。
- InMemorySessionStore 支持进程内多 Turn 历史。
- BasicContextBuilder 每轮读取 SessionSnapshot 和 MemoryProjection。
- ReadOnlyPermissionPolicy 在 ToolRegistry 执行前作出 allow/deny。
- RuntimeEvent、CancellationToken 与结构化用户输入端口。
- Rich/prompt-toolkit CLI、`/help`、`/exit`、`/quit` 和标准输入回退。
- v0.0.3 wheel 与 sdist。

## 验证事实

- 28 个无网络测试全部通过。
- Ruff 与 basedpyright 零问题。
- one-shot 实际完成 `Grep → Read → final`。
- schema v1 JSON 模式只输出一个 JSON 文档。
- 脚本输入实际完成 `/help → hello → /exit` 交互场景。
- wheel/sdist 构建及 uv 隔离 tool 环境安装通过。
- 源码中只有一个 `class AgentLoop`，不存在 RuntimeRunner 实现。

## 设计偏差

- Windows 重定向输入没有 Console Screen Buffer，prompt-toolkit 无法初始化；CLI 在真实终端使用
  prompt-toolkit，在重定向输入中回退到异步标准输入，从而保持同一 InteractiveShell。
- `app.run_prompt` 继续作为 M1 兼容入口，但只调用 composition root，不持有第二循环。

## 遗留风险

- M3 Session 只在内存中；进程退出后的持久化和恢复属于 M5。
- ReadOnlyPermissionPolicy 只有 allow/deny；ASK、grant 与权限暂停属于 M4。
- RuntimeEvent 是展示活动，不具备 durable SessionEvent 的恢复语义。
- Context 和 Memory 当前仅建立真实边界，预算压缩与长期存储分别在 M6、M7 实现。

## 复杂度快照

- 主体 Python：38 个文件，约 2,085 行。
- 最大模块：AgentLoop 260 行；未触发 800 行复查线。
- RuntimeEvent：5 种；durable SessionEvent：0；Tool：3。
- 测试：8 个文件、28 个测试、约 835 行。
- 直接运行时依赖：4（OpenAI SDK、Pydantic、prompt-toolkit、Rich）。

## M4 输入

- 以当前 ToolRegistry、ReadOnlyPermissionPolicy 和 RuntimeEvent 为迁移基线。
- 先设计 Edit preview/snapshot/stale-write，再接 PermissionRequest 和 ASK。
- Provider、Session、Context 与 CLI 不直接执行写入或 Shell。
- 写入、权限拒绝、用户暂停和验证必须形成一个可运行纵向场景。
