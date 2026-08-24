# M1 验收

## 自动化命令

```powershell
uv sync --dev --locked
uv run ruff check .
uv run basedpyright
uv run pytest
uv build
uv run agent --help
uv run agent -p "用一句话概括当前目录"
uv run agent -p "用一句话概括当前目录" --json
```

## 通过条件

- 所有命令退出码为 0；
- 核心测试不需要网络和 API Key；
- JSON 模式 stdout 可以被 `json.loads` 直接解析；
- Fake Provider 请求内容被测试断言；
- OpenAI-compatible 转换、Usage 和至少四类错误被确定性测试覆盖；
- wheel/sdist 可构建，console script 可运行。

真实 Provider smoke 是人工检查，不进入确定性 CI。
