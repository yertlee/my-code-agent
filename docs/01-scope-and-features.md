# 功能范围与扩展路线

## 1. Agent Kernel

Kernel 只包含驱动任何 Agent preset 都需要的机制：

| 能力 | 当前实现 | 扩展方式 |
| --- | --- | --- |
| 内部协议 | ModelRequest、stream events、ToolCall、ToolResult、TurnResult | Provider-neutral DTO |
| Agent 驱动 | 唯一 `AgentLoop` | 通过 contracts 使用能力，不导入具体插件 |
| 模型能力 | `ChatProvider` | 传入 Application composition |
| 工具能力 | `Tool` + `ToolRegistry` | 注册 Tool 实例 |
| 权限能力 | `PermissionPolicy` + `PermissionManager` | 注入 policy |
| Session 能力 | `SessionStore` | 注入 store |
| Context 能力 | `ContextBuilder` | 注入 builder |
| 运行观察 | `EventSink` | 注入 CLI/测试 renderer |
| 生命周期 | `AgentApplication` | 统一创建、运行、取消和关闭 |

Kernel 本身不决定使用哪些模型、工具和界面；默认 Coding preset 在 composition root 装配它们。

## 2. v0.0.4 Coding preset

当前可运行 preset 包含：

- OpenAI-compatible Provider 与 Fake Provider 演示适配器；
- `Read`、`Glob`、`Grep`、`Edit`、`Shell`、`TodoWrite`；
- Workspace 路径边界、Tool 参数校验和输出预算；
- plan、standard、bypass 权限模式；
- Edit Diff、快照复查和原子替换；
- PowerShell timeout、进程终止和输出截断；
- 内存多 Turn Session 与基础 System Prompt；
- Rich/prompt-toolkit interactive CLI、one-shot 和 JSON 结果。

## 3. 后续能力扩展

每项能力单独形成一个纵向里程碑，并通过现有 Kernel seam 接入：

| 扩展 | 用户故事 | 接入点 |
| --- | --- | --- |
| Durable Session | 退出后列出并恢复同一会话 | `SessionStore` + Application create/resume |
| Context strategy | 长会话在预算内继续运行 | `ContextBuilder` |
| Memory | 新 Session 复用带来源的项目知识 | M7 当期新增 `MemoryStore` seam |
| Provider plugin | 增加 Anthropic/Responses 等后端 | `ChatProvider` registry |
| Tool plugin | 增加项目工具或第三方能力 | `ToolRegistry` |
| Preset | 选择一组 Provider、Tools 和 policies | composition 配置 |

## 4. 插件成熟度

### v0.1.0 之前

- 插件是实现公开 contract 的 Python 对象。
- 内置 preset 通过显式 factory/registry 装配。
- 每个扩展可以独立测试，且不修改 AgentLoop。

### v0.1.0 收口阶段

- 冻结首批公开 contracts。
- 增加轻量 preset 配置和 Python package discovery。
- 提供一个最小外部 Tool plugin 示例。

动态卸载、依赖图、热重载和完整插件市场需要独立用户故事，不进入首个可读版本。

## 5. JSON 用户入口

`agent -p "任务" --json` 输出版本化 TurnResult，至少包含：

```json
{
  "schema_version": 1,
  "session_id": "ses_...",
  "turn_id": "turn_...",
  "status": "completed",
  "stop_reason": "completed",
  "output_text": "...",
  "verified": null,
  "verification": [],
  "tools_used": ["Read"],
  "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
  "error": null,
  "pending_input": null
}
```

该合同只在对应能力真实实现时增加字段；未来插件内部状态不直接泄漏到 Kernel TurnResult。

## 6. 功能进入清单

提议一个扩展时只回答六个问题：

1. 用户能观察到什么？
2. 它挂在哪个 Kernel seam？
3. 默认 preset 是否启用？
4. 最小正常场景是什么？
5. 唯一需要优先保护的失败是什么？
6. 是否在当前里程碑预算内？
