# 生产运行手册

## 发布顺序

1. 安装 `pg_dump/pg_restore` 与 `age`，配置 `BACKUP_AGE_RECIPIENT`，为 PostgreSQL 和 `PRIVATE_UPLOAD_DIR` 创建同一时间点加密备份。
2. 执行 `alembic upgrade head`，成功后再启动 API 和独立 worker。
3. 访问 `/api/health` 检查进程存活，访问 `/api/ready` 检查数据库版本、worker 心跳与 outbox 深度。
4. 小程序 production 构建通过门禁后再上传体验版；完成学生和管理员冒烟测试后发布。

## 回滚

- 代码回滚：切回上一镜像；若旧版本不兼容新 schema，必须先在隔离环境验证恢复备份，不允许直接执行破坏性 downgrade。
- 数据恢复：停止 API/worker，设置 `DATABASE_BACKUP`、`MEDIA_BACKUP`、`PRIVATE_UPLOAD_DIR` 和受控保存的 `BACKUP_AGE_IDENTITY` 后执行 `deploy/restore.sh`。
- 每季度至少在隔离环境演练一次恢复，记录备份时间、恢复完成时间、丢失窗口和负责人。

## 运行检查

- `/api/ready` 返回 503：检查数据库、Alembic revision 和 `worker_last_success_at`。
- `outbox_pending` 持续增长：检查微信凭据、模板、worker 日志与失败通知。
- 日志使用 JSON 行并包含 `request_id` 或 `job_id`，排障时以该编号串联请求或任务。
- API 与 worker 必须分开运行；PostgreSQL advisory lock 会阻止两个 worker 同时执行同一分钟任务。

## 密钥轮换与事故响应

- `SECRET_KEY`、数据库密码和微信 AppSecret 只通过学校密钥库/部署环境注入。
- JWT 密钥轮换会使现有登录失效，应提前通知并在低峰执行。
- 发现敏感媒体泄露时先停用相关媒体记录、保留审计日志，再通知学校安全负责人；禁止在公开 Issue 放入真实个人数据。
