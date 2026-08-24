# M2 进度

## 2026-08-24

- M1 已确认可用。
- OpenAI Chat Completions 与 DeepSeek V4 Tool Call/Reasoning replay 契约已核对。
- 已实现 Provider-neutral tool 协议、Workspace、Tool Registry、Read/Glob/Grep 和唯一
  RuntimeRunner。
- Fake `Grep → Read → final` 场景及 OpenAI-compatible 流式 tool call 已接入 CLI。
- 21 个无网络测试通过；Ruff、basedpyright、本地构建和 clean install 已验收。
- 当前环境没有 `DEEPSEEK_API_KEY`，M2 真实 DeepSeek tool-call smoke 留作人工可选验证；Key
  不进入仓库或 CI。
- 主实现提交 `b4f5e5b` 已推送；GitHub Actions CI run `32701335489` 全部通过。
