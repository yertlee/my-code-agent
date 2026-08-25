# M4 行为场景

## S1：确认后修改并验证

模型先 Read，再请求 Edit。CLI 展示 Diff；用户选择 allow once 后 AgentLoop 复查快照、原子替换，
随后模型请求 Shell 运行测试。Shell 再次确认，退出码和输出作为 ToolResult 返回模型。

## S2：拒绝修改

用户拒绝 Edit 后，原文件不变；原 tool_call 得到 permission_denied ToolResult，模型可以解释、
修订方案或结束。

## S3：stale snapshot

Diff 展示后由外部进程修改目标文件。用户允许时 Edit 检测摘要变化并返回 stale_snapshot；外部
内容保持不变，模型必须重新 Read 后再提出修改。

## S4：权限模式

- standard：Read/Glob/Grep/TodoWrite allow，Edit/Shell ask。
- plan：Edit/Shell deny，不出现可绕过的确认入口。
- bypass：Edit/Shell allow，Edit 仍产生 Diff 活动和快照复查。

## S5：Session grant

用户对一个 Edit 路径选择 allow session；同 Session 对相同规范化路径的后续 Edit 自动允许，
其他路径仍询问。Shell 不接受 allow session。

## S6：Shell 边界

Shell cwd 必须位于 Workspace；命令超时或取消时终止进程树；stdout/stderr 分别截断；非零退出码
返回普通错误 ToolResult，不被解释为任务正确。

## S7：非交互 JSON

`--json` 不读取 stdin。遇到 ASK 时返回 waiting 状态、权限请求摘要和退出码 3；跨进程恢复在
M5 实现。

## S8：Todo revision

TodoWrite 使用 expected_revision 更新完整快照；revision 不匹配、重复 ID、多个 in_progress 或
blocked 缺少原因时返回结构化工具错误。
