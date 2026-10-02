# 05–11 教程、部署与恢复验证报告

日期：2026-10-02。partner工作区，基线提交f812b31ef7fc0ab80eab41434f872ed9e8254f09。01–11累计改动尚未提交/推送/main合并/创建Release/部署学校。报告只记录真实本地运行，学校资源与验收另列。

## 本轮完成范围

| 编号 | 修改与结果 | 仍依赖学校的验收 |
|---|---|---|
| 05 | README去掉旧测试数字、旧迁移、手改seed密码；增加恢复/换密、订单/待办、区间限制、审计与鉴权照片链接 | 学校实际建号与核验责任 |
| 06 | README改为角色导航，列当前候选状态、资源责任、Windows/macOS/Linux快速启动、生产/演示边界和专门清单 | 接收人员独立从入口找到教程 |
| 07 | USER_GUIDE按实际页面按钮写学生/辅导员/管理员流程，含首次换密、人工凭证、消息、限制和导出 | 非开发人员完整操作、真实脱敏截图与手机验证未冒充完成 |
| 08 | DEPLOYMENT_GUIDE提供固定提交、Compose与直接Python、空库迁移/基础数据/建号、HTTPS、启停/持久化/升级回滚；根Compose.env模板和systemd样例 | 学校Linux/systemd、域名/证书、宿主机开机恢复、业务批准 |
| 09 | WECHAT_SETUP、README、AGENTS/CLAUDE统一源码与dist入口、构建注入、AppID权限、两种环境配置、API/worker微信变量及发布责任 | 当前公众平台权限/密钥/模板/真实微信消息及发布 |
| 10 | ARCHITECTURE、REQUIREMENTS_TRACEABILITY、ROADMAP、CHANGELOG与AI约定同步domain、20261002_03、账号/审计功能及证据边界 | 会议容量、申请前预览、冰箱登记、可信身份和隐私/权利决定 |
| 11 | 备份从仅私密图升级为数据库+public/private图成套age密文与清单；停写声明、空目标、URL匹配、损坏检测、安全归档和媒体属主；实际PostgreSQL/Compose恢复成功 | 学校运维在批准策略下独立演练、恢复点/保留期限与签字 |

当前发布门槛没有放宽，第12–14的PR/评审/main合并、候选/正式发布规则和交付包仍待后续执行。历史报告保留原日期，不盲改旧测试结果。

## 实际运行

- 后端`../.venv/bin/python -m pytest -q`：**48通过、2跳过、1个既有Starlette/httpx弃用警告**，约17秒。本机虚拟环境Python3.13。跳过的2项是原有PostgreSQL并发作业，本轮恢复演练不是它们，不能改写为通过。
- `npm test`：**30通过**（构建10、逻辑/请求/交互16、发布规则4），无失败/跳过。
- `python3 scripts/check-handover-docs.py`：15个当前文档、62个本地链接/锚点校验通过。
- Python脚本编译与两个shell入口语法检查通过；测试结束未留下自己的临时容器/卷。
- `npm run release:check`和`git diff --check`：通过；文档基线检查不是学校签字或发布许可。
- 将实际小程序源码复制到临时目录，用示例HTTPS、已有AppID、版本/完整提交字段执行production构建并校验：64文件、AppID/HTTPS正确、运行时覆盖关闭。仅验证命令与配置，示例域名不是学校部署，临时产物已清理，未作为正式交付包。
- 实际构建ops镜像成功（Linux ARM64、PostgreSQL16客户端、age、Python3.12+标准库工具）；初次依赖下载使用已提供7898代理解决本机Docker网络解析，代理未写入正式配置。
- `python3 scripts/verify-deployment-recovery.py`：两随机命名临时Compose项目，使用真实PostgreSQL16、实际API/独立worker和虚构照片/账号，完成下列验证。未连接学校或原有演示库，清理仅限自己的临时项目/卷/网络/密钥。

### 部署与恢复闭环

1. 空库迁移至20261002_03，users=0；受控基础初始化12/10，重复0/0，不产生演示账号；创建虚构正式管理员。
2. 启动真实API和worker，ready为200、revision正确、worker心跳有效。
3. 虚构学生注册、上传玉兰卡、创建预约；仅为演练生成留言资格，直接推进该虚构订单为completed，再经HTTP上传/发布公开留言图。该推进不是正常用户操作验收。
4. 公开图按字节读取；私密图管理员鉴权可读、匿名401。重启db/API/worker后照片仍可读。
5. 停止源API/worker，生成age密钥，备份数据库和两个媒体目录；成套目录只有两个密文和manifest，临时明文已清理。
6. 新空库健康等待后，拒绝未停写声明、错误迁移目标、错误驱动URL、被损坏密文、非空数据库，未覆盖既有哨兵记录；成功恢复后再次恢复拒绝非空媒体目录。
7. 正常空目标恢复，**7张表的完整行数据摘要一致**：users、rooms、room_scene_rules、reservations、private_media、space_messages、admin_audit_logs。其他schema内容由实际转储恢复，未宣称逐表摘要全库验证。
8. 校正照片属主给app，显式运行同目标迁移，启动恢复API/worker；新登录成功、学生历史订单存在、两类图字节一致并正确鉴权；恢复项目再次重启后仍可读取订单与图。

首次试跑发现新库尚未就绪时恢复步骤可能过早运行；已在教程与演练增加`up -d --wait --wait-timeout 60 db`。损坏测试改用容器内写入，避免宿主机挂载同步时序影响错误分支。改正后完成部署/备份/恢复演练；最终代码含驱动URL门禁复跑通过，33.9秒完成完整演练。

## 命令和复现

从仓库根目录：

```sh
docker build -t duxue-handover-local:01-02 backend
docker build -t duxue-ops-local:05-11 -f deploy/Dockerfile.ops .
python3 scripts/verify-deployment-recovery.py
npm test
npm run release:check
python3 scripts/check-handover-docs.py
cd backend
../.venv/bin/python -m pytest -q
```

学校首次部署按 [部署指南](DEPLOYMENT_GUIDE.md)，备份/空目标恢复与直接Python配置按 [运行手册](OPERATIONS_RUNBOOK.md)，业务按 [使用教程](USER_GUIDE.md)，平台/手机按 [微信联调](WECHAT_SETUP.md)。

## 未据此宣称完成的事项

没有执行学校公众平台或自动上传发布，没有真实域名/HTTPS和微信消息，没有学校Linux的systemd/主机重启，没有非开发人员操作或真实产品截图，没有确认会议容量/预览/冰箱/可信身份/隐私/权利；未执行远程CI、main合并、标签或交付打包。教程和本地演练已就绪，以上学校验收及12–14步骤继续推进。
