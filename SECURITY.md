# 安全政策

## 支持范围

当前只支持 `main` 上最新的 `v0.x` 校内试点候选。尚未发布的历史云函数和 `frontend/` 参考实现不属于生产支持范围。

## 私下报告

请不要用公开 Issue 提交漏洞、真实学号、手机号、照片、令牌或服务器信息。优先通过仓库的 [Private vulnerability report](https://github.com/syann2788-arch/DUT-duxue-space-booking/security/advisories/new) 报告；若该入口不可用，请通过学校已确认的内部安全联系人私下联系维护者。

维护目标：2 个工作日内确认收到，P0 在确认后立即停止发布并给出缓解方案；修复完成前不公开可利用细节。学校正式试点前必须指定有效的校内安全联系人并演练一次报告流程。

## 安全基线

- 生产必须使用 PostgreSQL、强随机 `SECRET_KEY`、HTTPS 与 `ALLOW_OPEN_REGISTRATION=false`。
- 不提交真实 `.env`、个人信息、AppSecret、管理员密码或生产数据库。
- P0 安全 Issue 未关闭或没有书面风险接受时不得发布。
