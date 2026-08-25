# M3 目标：架构骨架与交互式 CLI

版本目标：v0.0.3。

M3 把已完成的只读模型—工具循环迁入完整 Agent 的正式模块边界，并提供可连续输入的终端界面。
用户既可以继续使用 `agent -p "任务"`，也可以直接运行 `agent` 进入交互式会话；两种入口必须
经过同一个 Application、AgentLoop、Session、Context、Permission 和 Tool 调用链。

## 用户可观察结果

- `agent` 启动交互式 CLI，接受连续任务以及 `/help`、`/exit`。
- 同一交互进程中的后续任务能够看到此前消息和工具结果。
- 模型文本、工具开始/完成和 Turn 终态通过结构化运行活动展示。
- `agent -p` 与 schema v1 JSON 输出保持兼容。
- Ctrl-C 可以取消当前 Turn 或退出空闲交互界面，不产生 Python traceback。

## 工程结果

- 唯一正式循环为 `agent.AgentLoop`。
- Provider 生命周期由 Application 管理，允许一个交互会话执行多个 Turn。
- `app`、`agent`、`runtime`、`session`、`context`、`memory`、`permissions` 都有真实调用路径。
- M3 使用内存 Session、基础 ContextBuilder、空 Memory 投影和只读权限策略；不提前实现 M4–M7。

## 非目标

- 文件写入、Shell、TodoWrite 和权限询问。
- JSONL 持久化、Session list/resume/status。
- Token 水位、上下文压缩和长期 Memory 存储。
- Textual TUI。
