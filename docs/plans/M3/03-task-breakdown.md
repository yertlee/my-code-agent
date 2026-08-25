# M3 任务拆分

## T1：依赖与运行时原语

- 增加 Rich、prompt-toolkit 依赖。
- 实现 RuntimeEvent、EventSink、CancellationToken 和输入端口。
- 增加对应 Unit tests。

## T2：最小协作者

- 实现 InMemorySessionStore 与 SessionSnapshot。
- 实现 EmptyMemoryRetriever 与 MemoryProjection。
- 实现 BasicContextBuilder。
- 实现 ReadOnlyPermissionPolicy。
- 分别增加 Unit tests。

## T3：AgentLoop 迁移

- 将 RuntimeRunner 的唯一循环迁到 `agent/loop.py`。
- 接入 Session、Context、Memory、Permission 和 RuntimeEvent。
- 保持模型/工具限制、reasoning 回放、错误和取消行为。
- 迁移并扩充 AgentLoop tests。

## T4：Application 与 composition root

- 将单文件 app 迁为 app package。
- 实现 AgentApplication、build_application 和兼容 run_prompt。
- 明确 Provider close 生命周期。
- 增加多 Turn integration tests。

## T5：交互式 CLI

- `-p/--prompt` 改为可选。
- 实现 Rich renderer 和 prompt-toolkit 输入。
- 实现 `/help`、`/exit`、空输入与未知命令。
- 保持 JSON one-shot 契约。

## T6：收口

- 更新版本、README、PROJECT_STATUS 和代码阅读入口。
- 运行 pytest、Ruff、basedpyright、build 和 CLI 场景。
- 记录进度、Closeout、复杂度和偏差。
