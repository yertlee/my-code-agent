# M5 Closeout

## 1. 交付结果

M5 完成一条跨进程纵向链路：第一个 Application 把 Edit 权限等待追加到 JSONL，第二个 Application
重放同一 Session、claim request、校验确认内容、执行工具，并通过原 AgentLoop 生成最终回答。

CLI 入口：

```powershell
agent -p "创建 demo.txt" --session-dir .coding-agent/sessions --json
agent --list-sessions --session-dir .coding-agent/sessions --json
agent --resume <session_id> --permission-choice allow_once `
  --session-dir .coding-agent/sessions --json
```

## 2. Durable facts

| SessionEvent | producer | reducer 结果 |
| --- | --- | --- |
| `turn_started` | `begin_turn` | user message |
| `message_appended` | `append_message` | assistant/tool message |
| `usage_added` | `add_usage` | 累计 Usage |
| `permission_pending` | `save_pending` | 未处理 request |
| `permission_claimed` | `claim_pending` | request 不再可恢复 |

JSONL 是唯一持久化事实源。RuntimeEvent 保持 ephemeral，list/status 直接扫描并重放 JSONL。

## 3. 安全语义

- claim 在副作用前 append、flush、fsync；
- 已 claim 的 request 无法再次恢复；
- 原始 ToolCall 在恢复时重新 prepare；
- PermissionRequest 与 preview fingerprint 匹配后才执行；
- 确认内容变化产生 `stale_snapshot` ToolResult，文件保持当前状态。

## 4. 复杂度

| 指标 | M5 实际 | 门禁 |
| --- | ---: | ---: |
| 新增产品源码 | 713 行 | ≤ 1,000 |
| 新增产品模块 | 4 个 | ≤ 6 |
| 领域概念 | 3 个 | ≤ 3 |
| Durable event | 5 类 | ≤ 7 |
| AgentLoop | 467 行 | ≤ 500 |
| Agent Kernel | 1,119 行 | ≤ 2,000 |
| 产品源码总量 | 3,815 行 | ≤ 8,000 |
| Runtime dependency | +0 | 新增需批准 |

新增模块：`session/jsonl.py`、`session/codec.py`、`app/session_commands.py`、`app/arguments.py`。

## 5. 验收

- 49 项自动化测试通过；
- Ruff 通过；
- basedpyright 通过；
- wheel/sdist 构建通过；
- CLI help、create/list/resume smoke 通过；
- 自定义 Tool extension 仍保持 AgentLoop 零修改。

## 6. 下一输入

M6 开始前冻结 TokenEstimator、误差策略和一个渐进压缩用户故事。Context strategy 继续通过
ContextBuilder 接入，并保持 JSONL Session 事实不变。
