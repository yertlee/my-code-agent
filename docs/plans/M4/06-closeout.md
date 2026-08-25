# M4 Closeout

状态：完成。

## 实际交付

- `PermissionManager` 统一执行 plan/standard/bypass，策略硬拒绝优先于 grant。
- standard 模式对 Edit/Shell 返回结构化 PermissionRequest；AgentLoop 保存可信 prepared call 并
  通过 request ID 恢复，CLI 不接收候选写入内容。
- Edit 支持 create/replace/delete、唯一匹配、unified diff、SHA-256 快照复查和同目录原子替换。
- allow_session 仅适用于同一 Application 内相同规范化 Edit 路径；Shell 始终逐次确认。
- PowerShell 使用结构化进程参数、固定 Workspace cwd、超时、进程树终止和 stdout/stderr 独立预算。
- TodoWrite 使用完整快照、expected_revision、唯一 ID、单 in_progress 与 blocked reason 约束。
- plain 与 interactive CLI 可以继续权限等待；JSON 返回 waiting/pending_input 和退出码 3。

## 验证事实

- `uv run pytest -q`：39 项通过，无网络依赖。
- `uv run ruff check .`：通过。
- `uv run basedpyright`：0 error、0 warning。
- `uv build`：sdist 与 wheel 构建通过。
- wheel 隔离运行：`agent --version` 与 JSON 文本场景通过。
- CLI 写入场景：显示 Edit Diff，确认后创建文件，再次确认后由 PowerShell 读回，场景结束后无
  演示文件残留。
- JSON 写入场景：不读取 stdin，返回 waiting 与退出码 3，目标文件未创建。

## 与设计的偏差

- M4 的 Permission pending、Todo 和 Session grant 仅存在于当前进程；这是 M4 设计中的阶段边界，
  M5 将把等待事实写入 JSONL 并从 SessionView 重建。
- waiting 当前会发出一次 `TURN_FINISHED` 活动，恢复完成后再次发出；M5 持久化事件设计需要把
  “本次运行返回”与“逻辑 Turn 终态”区分开。
- 权限等待时间不计入恢复后的新一段 turn timeout；M5 应将运行段 deadline 明确写入状态协议。

## 复杂度快照

- 核心 Python 源码约 3.2k 行，测试约 1.2k 行。
- 最大模块为 `agent/loop.py`，约 400 行，未触发 800 行职责复查线。
- 正式模型—工具循环仍只有一个 `AgentLoop`。

## M5 输入

1. 以 append-only JSONL 作为唯一持久化写入源，实现 event/writer/store/reducer/SessionView。
2. 将 M4 进程内 pending permission 投影为可重放事件；恢复时只接受 request ID 和用户选择。
3. 明确 tool started 未完成时的 uncertain settlement，不自动重放可能产生副作用的调用。
4. `session list/resume/status` 通过目录扫描完成，不在 M5 引入 SQLite。
5. create 与 resume 继续共用 composition root 和唯一 AgentLoop。
