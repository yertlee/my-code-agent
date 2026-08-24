# M2 验收

## 自动化

```powershell
uv sync --dev --locked
uv run ruff check .
uv run basedpyright
uv run pytest
uv build
uv run agent -p "找到 ProviderErrorKind 的定义" --fake-scenario readonly
uv run agent -p "找到 ProviderErrorKind 的定义" --fake-scenario readonly --json
```

## 通过条件

- Fake 场景至少完成 Grep → Read → final 三次模型请求；
- OpenAI-compatible 流式参数按 index 正确累积；
- DeepSeek reasoning_content 在 tool-call 轮次被保留；
- 越界、二进制、超限、未知工具和 malformed JSON 有确定性测试；
- model/tool/time 三类限制有明确终态；
- M1 文本与 JSON 行为保持兼容；
- wheel clean install 后 console script 可运行。

真实 DeepSeek smoke 为人工检查，不要求把 Key 放入 CI。
