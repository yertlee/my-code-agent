# 测试与评测策略

## 1. 测试目标

测试不仅证明正常路径能运行，还要证明 Agent 在概率输出、错误工具参数、中断和副作用面前保持可解释。

## 2. 测试分层

### 单元测试

- Provider 请求和响应转换。
- Tool Schema 与参数校验。
- Workspace 路径解析和 symlink 越界。
- Permission 决策与授权范围。
- Session Event 编解码和重放 reducer。
- Context Token 预算、估算误差边界和工具序列验证。
- Memory 作用域、来源和状态转换。

### 集成测试

- Fake Provider → RuntimeRunner → Fake/real temp workspace tool。
- 模型返回工具调用后继续生成最终文本。
- 权限 ASK → 用户允许 → 原始工具调用恢复。
- Edit 审批后文件被外部改变，写入被阻止。
- JSONL 尾部损坏后恢复。
- prompt-too-long → 压缩 → 有界重试。
- `--json` stdout 单对象、stderr 诊断和退出码契约。

### 场景测试

每个场景由脚本化 Fake Provider 驱动：

1. 阅读仓库并回答。
2. 修改一个函数并运行测试。
3. 用户拒绝修改并给出反馈。
4. 模型重复调用相同工具直到触发停滞或轮次限制。
5. 工具开始后进程中断，恢复标记 uncertain。
6. 超长输出进入 Artifact 并被再次读取。
7. 未验证完成与验证完成产生不同终态。
8. 文件修改后模型直接声称完成，被 Gate 反馈后主动运行验证。
9. Todo 仍有 pending 项时不能进入 completed。

### 真实模型评测

不进入核心 CI。使用固定的小型任务集记录：

- 任务成功率；
- 平均模型调用次数；
- 工具调用失败率；
- Token 使用；
- 总耗时；
- 权限请求数量；
- 未结算工具数量；
- 验证通过率。

## 3. Fake Provider 协议

Fake Provider 必须支持：

- 预设文本响应；
- 预设一个或多个 tool calls；
- 流式 delta；
- malformed arguments；
- timeout/rate limit/prompt-too-long；
- 截断的 tool call；
- Usage；
- 断言实际请求消息和 Tool Definition。

这样才能在不使用 API Key 的情况下验证完整 Agent Loop。

## 4. 关键不变量测试

- Provider 视图永远不以孤立 tool result 开头。
- 一个 tool call 最多有一个最终 tool result。
- 未授权写操作不会执行。
- 工作区之外的路径永远不会进入文件系统操作。
- 压缩不会改变 Session 原始事实数量。
- 恢复不会重放 completed 或 uncertain 副作用。
- P0 删除 SQLite 后仍可 list/resume Session；Session 扫描结果由 JSONL 决定。
- Secret 不出现在 `config show` 和标准 Trace 中。
- Shell 命令无论内容如何，在 standard 模式下都不能绕过 ASK。
- `AGENTS.md` 不能授予 Shell/Edit 权限或扩大 workspace。
- Durable SessionEvent 注册表不超过 14 种，UiEvent 不参与重放。

## 5. 故障注入

至少注入：

- 写 JSONL 过程中崩溃；
- Provider 在流式工具参数中断开；
- 权限确认前文件变化；
- Shell 超时且子进程未立即退出；
- Artifact 写入失败；
- Context 压缩模型返回无效结构；
- M6 SQLite Memory 索引不存在或损坏；
- Memory 来源文件已改变。

TokenEstimator 至少覆盖：已知 encoding、本地保守 fallback、协议消息/工具定义开销、估算值低于实际值时的安全余量、Provider Usage 回填和 prompt-too-long 兜底。真实 Provider 的 estimate/actual 漂移只做发布报告，不放入无网络 CI。

## 6. 发布门禁

```text
ruff check
basedpyright
pytest unit
pytest integration
pytest scenarios
wheel build + clean venv install
CLI --help smoke test
source size report
docs link and entrypoint check
```

真实 Provider smoke test 为人工发布检查，不是确定性 CI 门禁。

## 7. 完成定义

一个功能只有同时满足以下条件才完成：

- 用户可观察行为存在；
- 正常路径测试通过；
- 至少一个失败路径测试通过；
- 事件和恢复语义已定义；
- 文档链接到真实入口；
- 没有新增重复状态真相。
