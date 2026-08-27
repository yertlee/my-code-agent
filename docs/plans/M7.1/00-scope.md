# M7.1 Memory Writer Strategy Comparison

## 用户故事

在同一 Agent、Ledger、Retriever 与固定工具证据下，用户切换 `evidence` 或 `llm` Writer，并从统一
输出观察事实覆盖、噪声、拒绝、额外模型调用与 Token 差异。

## 实现边界

- 保持 AgentLoop、Session、Context、JSONL Ledger 与 Keyword Retriever 语义不变。
- `EvidenceMemoryWriter` 是零额外调用的确定性基线。
- `StructuredExtractionWriter` 复用当前 ChatProvider，ModelRequest 不携带工具。
- 自动候选必须引用本次 Observation 中真实、成功的 ToolResult `part_id`。
- 配置文件 Read 与 exit code 为 0 的 Shell 是首批自动提取入口。
- Provider、JSON 或候选校验失败进入 Memory 指标，不阻断 Agent 任务。

## 观测契约

`TurnResult.memory` 和 `MEMORY_WRITTEN` 事件至少提供：writer、proposed、accepted、rejected、written、
writer_model_calls、writer_usage 和 write_errors。

## 固定评测

`evals/memory_writer_cases.json` 固定五类输入：Python 配置、Node 测试脚本、成功测试命令、失败命令、
普通源码读取。`scripts/evaluate_memory_writers.py` 对两个 Writer 使用同一数据并输出：

- expected fact match / fact recall；
- accepted / rejected / noise；
- writer model calls；
- input/output tokens；
- 每案例错误码。

## 验收

1. Evidence 基线无需 API 且结果确定。
2. LLM 输出中的无效 kind、key、confidence 或 evidence 引用被拒绝。
3. LLM Provider/解析失败不改变 Agent 主任务终态。
4. 两种 Writer 共用 DefaultMemoryService、JSONL Ledger 与 Keyword Retriever。
5. Ruff、BasedPyright、全量测试和复杂度门禁通过。

首次真实结果见 [01-real-evaluation.md](01-real-evaluation.md)。
