# M4 验收

## 自动化门禁

```powershell
uv run pytest
uv run ruff check .
uv run basedpyright
uv build
```

## 固定场景

- allow once：Edit 修改目标文件，Shell 验证通过。
- deny：Edit 不改变文件，模型收到 permission_denied。
- stale：确认前外部修改文件，Agent 返回 stale_snapshot。
- plan：Edit/Shell 不产生副作用。
- bypass：无需 ASK 但保留 Diff 和工具活动。
- allow session：同路径第二次 Edit 自动允许，Shell 仍 ASK。
- JSON：权限 ASK 返回 waiting 和退出码 3，不读取 stdin。

## 退出标准

- 所有副作用都经过 PermissionManager。
- CLI 不持有可信 ToolCall 或候选写入内容。
- Edit 没有绕过 preview/snapshot/atomic replace 的执行入口。
- Shell timeout/cancel 不遗留测试进程。
- M3 one-shot、交互式、多 Turn 和只读场景保持通过。
