# M3 验收

## 自动化门禁

```powershell
uv run pytest
uv run ruff check .
uv run basedpyright
uv build
```

## one-shot 兼容

```powershell
uv run agent -p "找到 ProviderErrorKind 的定义" --fake-scenario readonly
uv run agent -p "hello" --fake-response "ok" --json
```

预期：第一个场景完成 Grep、Read 和 final；第二个场景 stdout 只有一个 JSON 文档。

## 交互式 CLI

```powershell
uv run agent --fake-response "interactive ok"
```

依次输入：

```text
/help
hello
/exit
```

预期：显示帮助、流式回答和正常退出；没有 traceback。

## 退出标准

- 所有自动化门禁通过。
- one-shot、JSON 和交互式三条入口通过同一 composition root。
- AgentLoop 只有一份实现。
- 七个核心包进入实际调用链。
- Provider 多 Turn 只在 Application 关闭时关闭。
- M4–M7 的功能没有被空壳实现宣称完成。
