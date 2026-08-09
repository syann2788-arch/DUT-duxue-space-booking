# 贡献指南

本项目当前是校内试点候选。提交前请先阅读 `README.md`、`AGENTS.md`、`SECURITY.md` 和 `docs/REVIEW_REMEDIATION.md`。

1. 从 `main` 创建短期分支；正式微信端只修改 `miniprogram/`，`frontend/` 仅供参考。
2. 一个 PR 聚焦一个可验收目标并关联 Issue；涉及数据模型时说明迁移与回滚。
3. 运行 `python -m pytest -q`（`backend/`）和 `npm run check`（`miniprogram/`）。
4. 不提交真实学号、手机号、照片、密钥、数据库或辅导员名单。
5. 新 Issue 应在 2 个工作日内标记优先级、owner、状态和目标版本；外部阻断项要注明依赖方。

行为要求：尊重师生隐私，基于证据讨论，禁止骚扰、歧视、泄露个人信息或利用安全问题伤害真实系统。维护者可移除违反这些要求的内容或参与者。
