# M5 任务

- [x] 定义 PendingPermission 与 Session backend contracts。
- [x] 实现 5 类 SessionEvent 的序列化与 reducer。
- [x] 实现 JsonlSessionStore append、replay、list/status。
- [x] AgentLoop 使用 SessionBackend 保存、查找和 claim 权限等待。
- [x] 恢复时重新 prepare 并验证 confirmation fingerprint。
- [x] Application 提供按 Session 查找 pending 的入口。
- [x] CLI 增加 session-dir、list-sessions、resume 和 permission-choice。
- [x] 完成跨进程恢复、at-most-once、损坏日志和 CLI 测试。
- [x] 更新 README、状态、版本与 Closeout。
- [ ] 运行 pytest、ruff、basedpyright、build、CLI smoke 和架构门禁。
