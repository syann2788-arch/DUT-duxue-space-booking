# 第12项：main合并流程与证据入口

日期：2026-10-02。范围：将partner上此前11个提交及01–11交付准备改动，通过PR验证和审核后合入main。此项不创建版本标签、Release，不部署学校服务器，不代替学校签字验收。

## 实际状态从哪里查看

- [交付准备PR #30](https://github.com/syann2788-arch/DUT-duxue-space-booking/pull/30)：partner → main，查看说明中的最新目标提交、CI链接与结果、审批和合并记录。PR说明维护该次执行的远程证据，不以本文件的本地测试数字替代CI。
- [Quality Gate运行记录](https://github.com/syann2788-arch/DUT-duxue-space-booking/actions/workflows/quality.yml)：核对对应PR/提交的运行，不把另一个分支或旧提交的绿色状态当成通过。
- [main提交记录](https://github.com/syann2788-arch/DUT-duxue-space-booking/commits/main/)：合并后确认目标提交已包含，并检查main推送触发的工作流。

## 已核验的实际main合并

用户已确认合并；PR #30于2026-10-02 15:34:09 UTC由llxzaq合入main，merge commit为ee3b0a72fd1e2ca52d464209ee2060f2f83185b5。刷新origin/main后核对包含head9fe29b64034523be35a847e3076573cc384f9948且文件树一致。[main运行37027900993](https://github.com/syann2788-arch/DUT-duxue-space-booking/actions/runs/37027900993)后端、小程序、PG和依赖审计全部成功。平台没有独立CODEOWNER Approve review，不将实际合并改写为不存在的审批；原始事实已保存于PR说明。第13–14继续独立执行。

## 第12项本地预检

- `npm test`：30通过；`npm run release:check`：通过。这是文档基线检查，不是学校批准发布。
- 普通后端pytest：01–11轮48通过/2项PG跳过，详见 [本轮交付报告](HANDOVER_DOCUMENTATION_REPORT.md)。第12项改动涉及PG测试生命周期，另行真实执行下述PG作业。
- 隔离PostgreSQL16、Python3.12镜像：空库迁移至20261002_03，`RUN_POSTGRES_TESTS=1 python -m pytest -q test_postgres_concurrency.py` **2通过（1.27秒）**；一项passlib/crypt弃用告警。验证同一空间并发预约只成功一次、两个worker竞争时仅一个取得leader锁。没有连接原有演示库或学校数据库。
- 原PG作业各测试使用独立`asyncio.run`，共享连接池可能跨事件循环复用并导致第二项无限等待；现每个测试在其事件循环关闭前释放连接池，锁就绪等待上限30秒，异常时释放并收尾持锁任务。
- CI后端作业新增`python ../scripts/check-handover-docs.py`，检查交付文档本地链接与锚点。

## 首次远程CI与修复

PR #30首次目标提交623589c4f19cf02577ba01d9dd364eebacb34286；实际测试临时合并提交09241792220f3acd38f47fd7d7ea994921da87cc。[运行37025576069](https://github.com/syann2788-arch/DUT-duxue-space-booking/actions/runs/37025576069)中后端、小程序、PostgreSQL成功，依赖审计失败，标签构建按预期跳过。依赖审计报告PyJWT2.13.0有13个已知漏洞。

升级至 [PyJWT2.15.1](https://github.com/jpadilla/pyjwt/releases/tag/2.15.1)，补应用认证令牌回归：有效令牌往返，过期、错误签名、非允许算法、无签名及畸形令牌拒绝。首次运行仅用于定位问题，不作为升级后最新目标提交通过的证据；最新完整CI结果保存于PR说明。

升级后本轮完整本地后端pytest：54通过/2项PG跳过（15.70秒）。跳过项仍由独立真实PostgreSQL作业执行。测试专用HMAC密钥采用足够长度；Starlette/httpx接口弃用告警不影响测试结果。

第二次运行 [37026593684](https://github.com/syann2788-arch/DUT-duxue-space-booking/actions/runs/37026593684)对应head1674efb4a827c0eb60f1afcf6f78d19cb4511ed4：后端、PostgreSQL、依赖审计成功，小程序作业因许可证测试硬编码旧PyJWT2.13.0失败。已改为从requirements.txt读取锁定版本，再核对许可证清单对应行，继续检查版本一致性。第二次运行同样不作为最新目标提交完整通过的证据。

## PR和合并门槛

1. 将完整交付准备修改提交、推送到partner，建立partner → main PR，按 [PR模板](../.github/pull_request_template.md)说明范围、验证、隐私、迁移、回滚和未完成的学校验收。
2. 最新PR必须有以下四个成功作业：`Backend tests`（含并行pytest隔离、空库迁移、文档链接）、`Miniprogram build policy`（30测试、基线、开发构建和完整性）、`PostgreSQL concurrency`（真实PostgreSQL两项）、`Dependency audit`。失败应修复后推送，再核对新的目标提交。
3. `Miniprogram release artifact`只在`v*`标签运行；PR跳过不阻断此项，也不能据此宣称正式构建已完成。本次不创建标签绕过第13项规则确认。
4. PR工作流一般测试临时合并提交；同时保存最新PR head SHA、运行ID/URL及其测试SHA。评审前或合并前若head变化，旧结果不能替代新结果。
5. 按 [贡献指南](../CONTRIBUTING.md)至少一名维护者审核。本次涉及工作流、生产部署和数据库变更，须CODEOWNER `syann2788-arch`审核。处理全部评审意见后，使用预期head SHA合并，防止合入未经检查的新提交。
6. 合并后刷新远程引用，确认main包含PR目标提交，并查看main触发的工作流。保存merge commit和运行链接。只有目标CI成功、所需审批和实际main合并齐备，才可将第12项标为完成。

若CI完成而审批尚未发生，应保留PR供所有者审核并明确阻塞原因，不降低检查要求或自行代替维护者审批。第13–14项继续独立执行。
