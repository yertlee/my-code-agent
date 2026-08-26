# M1–M4 Agent Kernel Baseline 审计

日期：2026-08-26。

## 1. 审计目标

确认 M1–M4 是否形成可阅读 Agent Kernel，识别能力归属和真实扩展 seam，并用自动门禁固定后续开发
尺度。审计范围包括产品源码、测试、正式文档、里程碑变更规模和当前依赖方向。

## 2. 结论

M1–M4 已经具备一条完整 Kernel spine：

```text
CLI
  -> AgentApplication
  -> AgentLoop
  -> ChatProvider / ContextBuilder / ToolRegistry / PermissionManager / SessionStore
  -> ToolResult / TurnResult
```

Provider、Tool、Permission、Session、Context 和 EventSink 都存在真实替换 seam。代码收口重点是让
这些 seam 只保留当前调用路径，并把具体 Coding 能力归到内置扩展。

## 3. 分里程碑审计

### M1：Provider Kernel

保留：Provider-neutral DTO、ChatProvider、Fake/OpenAI-compatible adapters、CLI/JSON 和 Provider 错误
归类。这些内容共同形成最小模型调用主线。

收口：测试直接通过 Application composition 运行，统一到正式入口。

### M2：Tool Kernel

保留：唯一模型—工具循环、Tool contract/registry、Workspace、Read/Glob/Grep、调用与时间限制。

结论：M2 的每个新增模块都在当前 Coding preset 中使用，职责边界清楚。

### M3：Application Kernel

保留：AgentLoop、AgentApplication、composition root、RuntimeEvent、CancellationToken、SessionStore、
ContextBuilder 和 interactive CLI。

收口：基础 ContextBuilder 只投影当前 System Prompt 与 Session；Memory contract 在 M7 用户故事到达
时创建。运行时输入由现有 TurnResult/pending_input 合同承担。

### M4：可控 Coding preset

保留：Edit、Shell、PermissionManager、prepared execution、Diff、stale snapshot、PowerShell timeout
与 TodoWrite。这些能力直接服务“确认后修改并验证”的固定演示。

收口：TodoWrite 持有自己的 TodoStore，ToolContext 只保留所有 Tool 共同需要的 Workspace。默认权限
策略统一覆盖读写和 Shell。

## 4. 当前能力归属

### Agent Kernel

- `agent/`
- `protocol/`
- `runtime/`
- `tools/base.py`
- `tools/registry.py`
- `app/application.py`
- `app/factory.py`

### 内置 extensions

- `providers/`
- `tools/readonly.py`、`edit.py`、`shell.py`、`todo.py`
- `permissions/`
- `session/`
- `context/`
- `workspace/`
- CLI renderers

## 5. 复杂度快照

| 指标 | 收口后 | 门禁 |
| --- | ---: | ---: |
| 产品 Python 源码 | 3,102 行 | v0.1.0 ≤ 8,000 |
| Agent Kernel | 1,040 行 | ≤ 2,000 |
| AgentLoop | 397 行 | ≤ 500 |
| 产品 Python 文件 | 38 | 按里程碑新增 ≤ 6 |
| Runtime dependencies | 4 | 新增需审核 |
| RuntimeEvent 类型 | 8 | 全部有 producer |
| 自动化测试 | 44 | 主路径和关键边界 |

## 6. 自动治理

`tests/architecture/test_kernel_guardrails.py` 检查：

- 产品、Kernel 和 AgentLoop 行数；
- 普通模块 300 行上限；
- runtime dependency allowlist；
- AgentLoop 不导入具体 Provider/Tool extensions；
- extensions 不导入 AgentLoop；
- 唯一 AgentLoop class；
- Kernel Protocol 不超过 5 个方法。

`tests/integration/test_kernel_extensions.py` 使用一个项目外形态的 Echo Tool 完成真实模型—工具循环，
证明 Tool extension 只通过 Registry 接入。

## 7. 下一步输入

后续每个里程碑以“一个 Kernel seam + 一个用户故事”推进。M5 到达时重新提取最小 Session 骨架，
只实现 JSONL 重放、权限等待恢复和副作用不重复所需的状态。
