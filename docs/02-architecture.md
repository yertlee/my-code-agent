# Agent Kernel 与扩展架构

## 1. Kernel Spine

```text
CLI / API
   |
   v
AgentApplication  <--- composition root / preset
   |
   v
AgentLoop
   |---- ChatProvider
   |---- ContextBuilder
   |---- ToolRegistry ---- Tool plugins
   |---- PermissionManager ---- PermissionPolicy
   |---- SessionStore
   `---- EventSink
```

`AgentLoop` 是默认且唯一的具体驱动。它只编排一次 Turn 的模型、工具、权限和停止条件，不拥有
Provider HTTP、文件实现、CLI 渲染或未来 Memory 算法。

## 2. Kernel 与能力实现

### Kernel

| 路径 | 责任 |
| --- | --- |
| `protocol/` | 模型、工具和 Turn 的公共数据词汇 |
| `agent/` | 唯一模型—工具循环与限制 |
| `runtime/` | cancellation 与 ephemeral activity |
| `tools/base.py`、`tools/registry.py` | Tool contract、注册与统一执行边界 |
| `app/application.py` | Agent 生命周期 |
| `app/factory.py` | 默认 preset 的 composition root |

### 内置能力实现

| 路径 | 提供的能力 |
| --- | --- |
| `providers/` | Fake 与 OpenAI-compatible ChatProvider |
| `tools/readonly.py` | Read/Glob/Grep plugins |
| `tools/edit.py` | Edit plugin |
| `tools/shell.py` | PowerShell plugin |
| `tools/todo.py` | TodoWrite plugin |
| `permissions/` | 默认权限策略与 manager |
| `session/` | 当前内存 SessionStore |
| `context/` | 当前基础 ContextBuilder |
| `workspace/` | 本地工作区能力 |
| `app/interactive.py`、`app/rendering.py` | CLI presentation |

## 3. 依赖规则

```text
CLI / preset factory
  -> Kernel contracts + capability implementations

AgentLoop
  -> contracts / registries only

Capability implementation
  -> protocol + its direct local dependency
  -X-> AgentLoop private state

protocol
  -> Python standard library only
```

硬约束：

- Provider、Tool、Session、Context 和 UI 扩展不能导入具体 `AgentLoop`。
- AgentLoop 不能导入 OpenAI adapter 或具体 Read/Edit/Shell/Todo Tool。
- 只有 composition root 选择默认实现和 preset。
- 一个能力只有在当前里程碑存在真实调用路径时才获得公开 contract。
- 同一用户行为只有一条 Application/AgentLoop 运行路径。

## 4. 当前 Turn Trace

```text
1. CLI 构造 Coding preset
2. Application 开始 Turn
3. SessionStore 记录当前进程内消息
4. ContextBuilder 构造 ModelRequest
5. ChatProvider 产生 text/tool_calls/usage
6. AgentLoop 把 ToolCall 交给 ToolRegistry.prepare
7. PermissionManager 返回 allow/ask/deny
8. ASK：Application 返回 waiting，CLI 仅提交 request id + choice
9. ALLOW：ToolRegistry.execute_prepared 执行
10. ToolResult 写回 SessionStore
11. AgentLoop 继续模型调用或返回 TurnResult
```

这条 Trace 是代码阅读和回归测试的主线。Session、Context 和 Memory 扩展必须加入该 Trace，不建立
平行控制流。

## 5. 轻量插件模型

首版插件模型由三个原语组成：

1. **Contract**：Protocol 或稳定 DTO，最多暴露完成能力所需的方法。
2. **Registration**：Registry 接受能力实例。
3. **Composition**：factory/preset 决定安装哪些实例。

一个 Tool plugin 的完整接入形式：

```python
class MyTool:
    definition = ToolDefinition(...)

    async def execute(self, arguments, context) -> ToolExecution:
        ...

registry = ToolRegistry((*coding_tools(), MyTool()))
```

AgentLoop 无需知道 `MyTool` 的包、配置或实现。

## 6. 架构参照

DeepSeek Harness 将 Session、System Prompt、Tools、Agent 和默认 Agent Loop 组织为可组合能力；其
扩展依赖公开 Agent 能力，而不依赖具体 loop。项目采用相同的“能力边界 + 默认驱动”思想，并使用
Python Protocol、Registry 与显式 composition 保持教学规模：

- [DeepSeek Harness Architecture](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md)
- [DeepSeek Harness Core](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/subsystems/core.md)
