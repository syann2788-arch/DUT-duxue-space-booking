# 交付修改01–02实施与验证记录

2026-10-02。本轮只处理生产基础数据初始化与镜像运维脚本，未实施清单03及以后项目；未提交、推送、合并或部署学校服务器。

## 实现

- 默认房间/场景规则从演示seed拆到`backend/app/reference_data.py`，沿用现有12个房间、10条规则，业务歧义仍待学校决定。
- `backend/init_reference_data.py`显式运行；先检查密钥及迁移，再在同一事务插入缺失记录。已有房间、规则、禁用状态、用户、密码和系统设置保留不变，初始化不创建账号。
- PostgreSQL初始化采用事务advisory lock，防止两个CLI同时插入重复数据；仅新增时记录初始化审计。
- Docker镜像纳入初始化、正式管理员建号、辅导员导入脚本，移出演示seed，保持非root运行。
- 独立凭据卷挂载`/app/credentials`，目录0700、导入文件0600；构建上下文排除.env、照片、数据库、凭据和缓存；.gitignore排除本地凭据目录。
- 运维手册增加直接Python/Compose首次部署顺序、交互建号、辅导员安全导入及可重复的隔离验证命令。

## 验证

1. 后端pytest：48通过、2项原有PostgreSQL专项在普通pytest中跳过；1条Starlette/httpx弃用提示。
2. npm test：23通过（构建3、业务/接口16、发布4）。
3. Docker镜像实际构建成功，镜像包含3个运维脚本、无.env/seed，非root用户可使用凭据目录；Compose配置在虚构变量下校验成功。
4. 镜像+临时PostgreSQL16从空库迁移到20261002_03；两个CLI并发运行，仅一个新增12房间/10规则；没有演示账号。
5. 修改房间容量/停用状态、规则容量/优先级/禁用状态后重新初始化，修改保留、零重复。
6. 通过正式建号脚本创建虚构管理员；导入虚构辅导员，凭据0600，首次登录限制业务操作、换密成功。
7. 实际FastAPI请求完成四场景申请，均返回201。
8. 单元回归还覆盖未迁移时拒绝初始化、缺失规则补回，以及账号和系统设置保持不变。
9. git diff --check通过；测试容器、数据库、凭据卷和网络已清理，未改动原有shuyuan.db。

本次容器验证来自Linux ARM64、Python3.12及PostgreSQL16；本地pytest使用Python3.13。复现脚本：`scripts/verify-container-handover.py`与`scripts/container-handover-smoke.py`。原有PostgreSQL预约竞争/worker leader测试不在本次容器脚本范围内，不能把它们的跳过标为通过。真实微信、学校部署、备份恢复及管理员验收仍需执行。

原始运行日志保存在开发工作区父目录`outputs/audit-2026-10-02/01-02-image-build.log`和`01-02-postgres-container.log`，未含学校密钥或真实个人数据。报告和复现代码可随源码交付。
