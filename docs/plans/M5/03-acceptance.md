# M5 验收

## 自动验收

```powershell
uv run pytest
uv run ruff check .
uv run basedpyright
uv build
uv run agent --help
```

必须覆盖：

1. JsonlSessionStore 对 messages、usage 和 pending 的重放。
2. 两个 Application 实例模拟两个进程，完成同一个等待中的 Edit。
3. request claim 后无法再次执行。
4. 文件变化导致 confirmation 校验失败且不写入。
5. Session list/status 来自目录扫描。
6. JSON CLI create/resume 各输出一个 TurnResult document。
7. 现有 M1–M4 测试全部通过。

## 预算

- 新增产品源码：不超过 1,000 行。
- 新增产品模块：不超过 6 个。
- 新增领域概念：SessionEvent、PendingPermission、SessionBackend。
- Durable event：5 类。
- Runtime dependency：0。
