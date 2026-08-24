# M1 Closeout

状态：完成，已发布到 GitHub main。

## 实际交付

- 11 个主体 Python 文件，507 行；没有工具循环和持久化状态。
- Fake 与 OpenAI-compatible Provider 共享一个最小 Protocol。
- 9 个无网络测试覆盖流式拼接、Usage、错误转换、JSON 和配置失败。
- `ruff check`、basedpyright、pytest、sdist/wheel build、clean install smoke 均通过。
- 主实现提交：`c5b236f`（`feat: complete M1 CLI provider slice`）。

## 与设计的偏差

- M1 没有引入 Rich/prompt-toolkit：one-shot 文本不需要展示层依赖，等交互模式出现时再引入。
- 没有运行真实 Provider smoke：当前没有用户提供的 API Key/测试服务；核心 CI 明确不依赖它。
- OpenAI-compatible 适配器使用 Chat Completions。官方建议新 OpenAI 项目优先考虑 Responses，
  但本项目按 ADR-009 先验证更容易讲解的兼容协议，Responses 保留为 P1 对照适配器。

## M2 输入

- 将模型请求迭代引入唯一 RuntimeRunner。
- 新增 ToolDefinition、ToolCall 和 ToolResult，但只接入 Read/Glob/Grep。
- Fake Provider 增加脚本化 tool call 与请求断言。
- 保持 M1 `TurnResult` 与 CLI JSON schema 向后兼容。
