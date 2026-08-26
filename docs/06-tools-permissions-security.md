# Tool plugins、权限与 Workspace

## 1. Tool contract

每个 Tool plugin 提供：

- 模型可见 `ToolDefinition`；
- Pydantic 参数校验；
- `execute()`；
- 需要 preview/权限快照时提供 `prepare()` 与 `execute_prepared()`。

Tool 返回统一 ToolExecution/ToolResult。ToolRegistry 负责 JSON 解码、输出预算和错误归一；Tool 不
决定 AgentLoop 是否继续。

## 2. 当前 Coding tools

| Tool | 行为 | 权限 |
| --- | --- | --- |
| Read | 读取 UTF-8 文本行范围 | allow |
| Glob | 查找 Workspace 文件 | allow |
| Grep | 搜索文本 | allow |
| Edit | create/replace/delete 单个 UTF-8 文件 | standard ASK |
| Shell | 在 Workspace cwd 运行 PowerShell | standard ASK every time |
| TodoWrite | 更新该 Tool plugin 自己的 revision snapshot | allow |

新增 Tool 通过 ToolRegistry 注册，不修改 AgentLoop。

## 3. Edit 安全链路

```text
validate arguments
  -> Workspace.resolve
  -> read UTF-8 snapshot
  -> build candidate
  -> unified diff + digest
  -> PermissionManager
  -> digest recheck
  -> same-directory temporary file
  -> flush/fsync
  -> os.replace
```

- create 要求目标不存在；
- replace 要求 old_text 存在且默认唯一；
- delete 只删除文件；
- snapshot 变化返回 `stale_snapshot`；
- 直接绕过 prepared permission pipeline 会返回 `permission_required`。

## 4. Shell 边界

- Windows PowerShell 是当前唯一 executor；
- cwd 必须由 Workspace 解析；
- standard 模式每次 ASK，只允许 deny/allow_once；
- command、cwd、timeout 和语法特征进入 preview；
- stdout/stderr 独立截断并保留 exit code；
- timeout/cancel 尝试终止进程树；
- exit code 0 只表示命令成功，不等于编码任务已经正确。

静态语法特征仅用于解释确认内容，不承担自动安全分类。

## 5. Permission plugin seam

PermissionPolicy 根据 request 与 mode 返回 allow/ask/deny。PermissionManager 负责：

- plan/standard/bypass mode；
- 当前 Application 内 exact-path Edit grant；
- hard deny 优先于 grant；
- 将用户 choice 转成 PermissionDecision。

模型、Tool 和 CLI 都不能直接创建 allow decision。CLI 只传递 request ID 与用户 choice。

## 6. Workspace 与信任边界

- 文件路径解析后必须位于固定 Workspace root；
- Tool 参数和模型文本都是不可信输入；
- Diff、ToolResult 和 Shell exit code 是程序生成的证据；
- 权限层降低 Agent 误操作，不构成 OS 沙箱；
- API Key 和完整环境变量值不进入 RuntimeEvent 或 TurnResult。

后续外部 Tool plugins 继续使用相同 ToolRegistry、Workspace 和 Permission seams。
