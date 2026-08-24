# M2 目标：只读工具循环

## 用户可观察结果

用户提出代码问题后，Agent 能调用 `Glob`、`Grep`、`Read` 在工作区内寻找证据，将工具结果
返回模型，并在同一 RuntimeRunner 中继续调用模型直到生成最终回答。

## 成功演示

```powershell
agent -p "找到 ProviderErrorKind 的定义并列出错误类型"
```

回答必须来自实际工具结果，并包含项目相对路径。

## 本里程碑不做

- Edit、Shell 和任何写入；
- 权限交互；
- Session JSONL 与恢复；
- Context 压缩、Todo 和 Memory。
