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

增强输出复跑结果如下：

| 指标 | 首次运行 | 候选审计运行 |
| --- | ---: | ---: |
| Fact recall | 1.00 | 1.00 |
| Proposed / accepted | 6 / 6 | 5 / 5 |
| Candidate delta | 未记录 | 0 |
| Writer model calls | 3 | 3 |
| Input tokens | 872 | 879 |
| Output tokens | 2,147 | 984 |
| Total tokens | 3,019 | 1,863 |

审计运行中的五条候选均直接对应标注事实并引用真实 evidence part。`successful_test_command` 只生成
`test.run_command` 一条事实，内容为 `uv run pytest`，没有重复或过度提取。失败 Shell 与普通源码 Read
继续保持零调用、零候选。

## 结论

- Evidence Writer 提供零额外调用、低信息密度的确定性基线。
- LLM Writer 在本数据集把 fact recall 从 0.20 提升到 1.00，同时每轮需要 3 次额外调用。
- 两次 LLM 输出 Token 分别为 2,147 和 984，说明成本与候选数量具有运行间波动。
- 当前候选质量满足 M7.1 验收；不同运行能否为同一事实生成稳定 key，作为后续独立评测维度。
