# 第12项：main合并流程与证据入口

日期：2026-10-02。范围：将partner上此前11个提交及01–11交付准备改动，通过PR验证和审核后合入main。此项不创建版本标签、Release，不部署学校服务器，不代替学校签字验收。

## 实际状态从哪里查看

- [仓库PR列表](https://github.com/syann2788-arch/DUT-duxue-space-booking/pulls)：找到partner → main的学校交付准备PR，查看说明中的目标提交、CI链接与结果、审批和合并记录。PR说明维护该次执行的远程证据，不以本文件的本地测试数字替代CI。
- [Quality Gate运行记录](https://github.com/syann2788-arch/DUT-duxue-space-booking/actions/workflows/quality.yml)：核对对应PR/提交的运行，不把另一个分支或旧提交的绿色状态当成通过。
- [main提交记录](https://github.com/syann2788-arch/DUT-duxue-space-booking/commits/main/)：合并后确认目标提交已包含，并检查main推送触发的工作流。

## 第12项本地预检

- `npm test`：30通过；`npm run release:check`：通过。这是文档基线检查，不是学校批准发布。
- 普通后端pytest：01–11轮48通过/2项PG跳过，详见 [本轮交付报告](HANDOVER_DOCUMENTATION_REPORT.md)。第12项改动涉及PG测试生命周期，另行真实执行下述PG作业。
- 隔离PostgreSQL16、Python3.12镜像：空库迁移至20261002_03，`RUN_POSTGRES_TESTS=1 python -m pytest -q test_postgres_concurrency.py` **2通过（1.27秒）**；一项passlib/crypt弃用告警。验证同一空间并发预约只成功一次、两个worker竞争时仅一个取得leader锁。没有连接原有演示库或学校数据库。
- 原PG作业各测试使用独立`asyncio.run`，共享连接池可能跨事件循环复用并导致第二项无限等待；现每个测试在其事件循环关闭前释放连接池，锁就绪等待上限30秒，异常时释放并收尾持锁任务。
- CI后端作业新增`python ../scripts/check-handover-docs.py`，检查交付文档本地链接与锚点。

## PR和合并门槛

1. 将完整交付准备修改提交、推送到partner，建立partner → main PR，按 [PR模板](../.github/pull_request_template.md)说明范围、验证、隐私、迁移、回滚和未完成的学校验收。
2. 最新PR必须有以下四个成功作业：`Backend tests`（含并行pytest隔离、空库迁移、文档链接）、`Miniprogram build policy`（30测试、基线、开发构建和完整性）、`PostgreSQL concurrency`（真实PostgreSQL两项）、`Dependency audit`。失败应修复后推送，再核对新的目标提交。
3. `Miniprogram release artifact`只在`v*`标签运行；PR跳过不阻断此项，也不能据此宣称正式构建已完成。本次不创建标签绕过第13项规则确认。
4. PR工作流一般测试临时合并提交；同时保存最新PR head SHA、运行ID/URL及其测试SHA。评审前或合并前若head变化，旧结果不能替代新结果。
5. 按 [贡献指南](../CONTRIBUTING.md)至少一名维护者审核。本次涉及工作流、生产部署和数据库变更，须CODEOWNER `syann2788-arch`审核。处理全部评审意见后，使用预期head SHA合并，防止合入未经检查的新提交。
6. 合并后刷新远程引用，确认main包含PR目标提交，并查看main触发的工作流。保存merge commit和运行链接。只有目标CI成功、所需审批和实际main合并齐备，才可将第12项标为完成。

若CI完成而审批尚未发生，应保留PR供所有者审核并明确阻塞原因，不降低检查要求或自行代替维护者审批。第13–14项继续独立执行。
