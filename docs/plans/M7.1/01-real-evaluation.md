# M7.1 首次真实 Writer 对比

- 评测日期：2026-08-27
- LLM：`deepseek-v4-flash`
- 数据集：`evals/memory_writer_cases.json`

## 结果

| 指标 | Evidence Writer | LLM Writer |
| --- | ---: | ---: |
| 匹配事实 | 1 / 5 | 5 / 5 |
| Fact recall | 0.20 | 1.00 |
| Proposed | 3 | 6 |
| Accepted | 3 | 6 |
| Rejected | 0 | 0 |
| Noise | 0 | 0 |
| Writer model calls | 0 | 3 |
| Input tokens | 0 | 872 |
| Output tokens | 0 | 2,147 |

LLM Writer 在三个可复用证据案例上各调用一次模型；失败 Shell 与普通源码 Read 被前置过滤，没有调用
模型或生成候选。与 Evidence 基线相比，它多匹配 4 个配置事实，额外消耗 3,019 Token。

## 候选审查

`successful_test_command` 的 expected fact 数量为 1，LLM Writer 接受了 2 个候选。v0.0.8 评测输出已
增加每条候选的 kind、key、content、confidence、evidence part 和 `candidate_delta`。使用同一数据集
再次运行后，可判断第二条候选属于有效补充、重复事实还是过度提取，再决定是否调整 Prompt 或上限。
