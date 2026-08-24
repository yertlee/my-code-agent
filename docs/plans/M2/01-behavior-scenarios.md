# M2 行为场景

## S1：搜索、读取、回答

Fake Provider 第一次调用 Grep，第二次调用 Read，第三次返回答案。每次请求都断言前一轮的
assistant tool call 与 tool result 成对存在。

## S2：未知或非法工具参数

未知工具、无效 JSON、缺字段和多余字段都变成普通错误 ToolResult，反馈给模型修正；不得让
Runner 崩溃或绕过 Workspace。

## S3：工作区越界

绝对路径、`..`、盘符路径和解析后逃离根目录的链接被拒绝。工具结果只能展示项目相对路径。

## S4：循环受限

模型持续调用工具时，Runner 在达到模型调用次数、工具轮次或总时间限制后返回明确的
`limited` 和 stop reason。

## S5：DeepSeek thinking tool call

Provider 累积流式 `reasoning_content` 与 tool-call arguments。发生工具调用时，assistant 的
reasoning 内容、tool calls 和后续 tool result 一起回传，满足 DeepSeek V4 多轮要求。
