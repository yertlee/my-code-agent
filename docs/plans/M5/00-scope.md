# M5：Durable Session

## 唯一用户故事

用户在一次 Edit 权限等待后退出进程，随后从同一 JSONL Session 恢复、提交权限选择，并让同一个
AgentLoop 继续执行工具和生成最终回答。

## 用户入口

```powershell
agent -p "创建 demo.txt" --session-dir .coding-agent/sessions --json
agent --list-sessions --session-dir .coding-agent/sessions --json
agent --resume <session_id> --permission-choice allow_once `
  --session-dir .coding-agent/sessions --json
```

交互模式下可以省略 `--permission-choice`，CLI 会显示持久化的权限问题并读取选择。

## 交付范围

- append-only JSONL Session backend；
- 由 JSONL reducer 重建消息、Usage 和未处理权限；
- 权限等待的跨进程 claim 与恢复；
- 目录扫描生成 Session list/status；
- CLI 创建、列出和恢复入口；
- 恢复前重新 prepare，并校验用户看到的确认内容；
- AgentLoop、Application 和 ContextBuilder 继续复用现有路径。

## 完成条件

1. 第一个进程返回 `waiting_for_permission`，目标文件保持原状。
2. 第二个进程从 JSONL 找到同一 request，允许后只执行一次 Edit。
3. 恢复后的 Provider request 包含恢复前的消息和新 ToolResult。
4. 已 claim 的 request 再次恢复会明确失败，文件内容不再变化。
5. JSONL 任一完整前缀都能重放；损坏行返回带行号的错误。
