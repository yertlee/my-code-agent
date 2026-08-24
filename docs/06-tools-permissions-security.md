# 工具、权限与安全

## 1. 工具设计原则

- Tool Definition 是模型可见合同。
- 参数必须在执行前进行严格 Schema 校验。
- 工具返回统一 `ToolResult`，错误也是普通结果，不通过异常泄漏协议细节。
- Tool 不决定 Agent 是否继续。
- 工具输出有大小预算，完整结果需要可恢复。
- 工具声明副作用、并发安全性和所需权限。

## 2. P0 工具集合

| 工具 | 副作用 | 默认权限 | 关键约束 |
| --- | --- | --- | --- |
| Read | 无 | allow | 文本、行范围、大小限制 |
| Glob | 无 | allow | 项目根目录内 |
| Grep | 无 | allow | 项目根目录内、结果预算 |
| Edit | 文件写入 | ask | 快照、Diff、原子写入 |
| Shell | 任意 | ask-every-time | P0 PowerShell、超时、输出预算、项目 cwd |
| TodoWrite | Session 状态 | allow | revision 与状态机校验 |

## 3. 唯一文件修改入口

`Edit` 支持：

- 创建新文件；
- 精确替换；
- 应用结构化 patch；
- 删除文件作为显式高风险操作。

执行流程：

```text
参数校验
  -> Workspace.resolve
  -> 读取当前快照
  -> 构造候选内容
  -> 生成可信 Diff
  -> 权限确认
  -> 重新校验快照
  -> 同目录临时文件
  -> flush/fsync（按平台能力）
  -> atomic replace
  -> 返回新哈希和统计
```

如果确认后文件已变化，操作返回 `stale_snapshot`，不得覆盖。

## 4. Workspace 边界

所有文件工具必须：

- 拒绝空路径、绝对路径和 `..` 穿越；
- 解析 symlink 后验证最终路径仍位于项目根；
- 区分不存在目标与父目录越界；
- 不通过 Shell 拼接文件操作参数；
- Windows 路径比较需处理盘符和大小写；
- 输出统一使用项目相对路径。

`Shell` 的进程权限仍与 Agent 进程账号相同。因此项目必须明确声明：权限策略降低误操作风险，但不是 OS 沙箱。

## 5. Permission 模型

### 决策

- `ALLOW_ONCE`
- `ALLOW_SESSION`（P0 仅用于可精确限定作用域的 Edit，不适用于 Shell）
- `DENY`
- `ASK`

### 风险级别

- `READ_ONLY`
- `WRITE_LOCAL`
- `PROCESS`
- `NETWORK`
- `DESTRUCTIVE`
- `UNKNOWN`

### 模式

- `standard`：读操作允许；Edit 按风险确认；每次 Shell 都询问。
- `plan`：禁止一切副作用，只允许分析与计划。
- `bypass`：用于受控测试环境；仍记录所有权限和 Diff 事件。

首版不提供“模型自行批准”或隐藏的自动允许逻辑。

## 6. Shell 规则

- P0 只实现 Windows PowerShell 启动、取消和进程树终止语义。
- 命令以结构化字符串记录，禁止日志中展开 Secret 环境变量。
- 默认 cwd 为项目根目录。
- 每次调用有 timeout 和最大输出字节数。
- stdout/stderr 分别捕获，结果包含 exit code。
- 超时后先请求终止，再使用经过测试的 Windows 进程树结束路径。
- 不把返回码为 0 自动解释为任务正确，只记录命令成功。
- standard 模式下所有 Shell 调用均为 `ASK`，只可 `ALLOW_ONCE` 或 `DENY`；不因命令看似只读而自动放行。
- `CommandInspection` 可提取首个可执行文件，并标记管道、重定向、变量展开和子表达式，供确认界面解释；它不是安全证明，也不改变 ASK 决策。
- 确认界面展示原始命令、cwd、timeout、将传入的环境变量名称和检测到的结构特征。P0 不声称支持通用 dry-run。

## 7. Prompt Injection 边界

仓库中的 README、注释、网页内容和工具输出均作为不可信数据。P0 唯一自动发现的规则文件是仓库根目录的 `AGENTS.md`：

- 不递归发现嵌套规则，也不自动读取 `CLAUDE.md` 或任意自定义文件名；额外名称是 P1 显式配置能力。
- `AGENTS.md` 放入低于系统/运行时策略的 project-guidance 区域，并在启动时显示路径与内容哈希；用户可禁用加载。
- 项目指导只能约束风格、测试和项目工作流，不能放宽权限、workspace、网络、Secret 或工具限制。
- 普通文件中的“忽略系统指令”等文本不改变运行时策略。
- 不承诺通过文本分类可靠识别所有 Prompt Injection；安全边界依赖 Schema、权限和 Workspace 代码。
- Memory 保存此类内容时必须保留来源类型和哈希，不能提升权限；源文件变化时对应 project_fact 失效。
- 外部 MCP 工具进入与本地工具相同的权限管线。

## 8. 日志与隐私

- 默认不记录 API Key、完整环境变量和认证 Header。
- 工具参数在 Trace 中按工具规则脱敏。
- Session 导出前扫描常见 Secret 模式并提示。
- Artifact 路径不能逃离 Session 数据目录。
- 用户可以删除整个 Session 或单条长期 Memory；删除 Session 是否安全擦除不作承诺。
