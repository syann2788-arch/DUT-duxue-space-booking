# 笃学书院空间预约系统 v2

大连理工大学笃学书院空间预约原生微信小程序 + FastAPI。当前版本 `0.1.0-rc.1` 为**尚未发布、待学校部署验收的候选准备稿**；本地已完成部分验证，尚未创建 Release 或部署到学校。本轮是否已合入 main 以对应 PR 的合并记录为准，流程和证据入口见 [main 合并说明](docs/MAIN_INTEGRATION_REPORT.md)。源码交接、微信发布与学校签字是后续不同步骤，当前发布门槛仍按仓库发布清单执行。

正式运行主线为 `miniprogram/` 和 `backend/`。`frontend/` 是历史 uni-app/H5 参考，`cloudfunctions/` 是第一版云函数参考。微信工具本地调试导入仓库根目录；体验/正式版本导入对应 `dist/miniprogram-*` 构建目录。

## 接收人员从哪里开始

| 角色 | 首先阅读 | 需要完成 |
|---|---|---|
| 学生、辅导员 | [使用教程](docs/USER_GUIDE.md) | 登录、申请、签到、清扫；辅导员首次换密 |
| 书院业务管理员 | [使用教程的管理员流程](docs/USER_GUIDE.md#管理员操作) | 审核、清扫复核、禁约、本人核验和密码恢复、导出 |
| 学校服务器运维 | [从空服务器部署](docs/DEPLOYMENT_GUIDE.md)、[运行与备份恢复](docs/OPERATIONS_RUNBOOK.md) | PostgreSQL、迁移、正式建号、HTTPS、API/worker、备份演练 |
| 小程序管理员/开发者 | [微信平台与真机配置](docs/WECHAT_SETUP.md)、[构建与校验](docs/BUILD_ARTIFACT_GUIDE.md) | 开发者权限、AppSecret/模板、合法域名、体验版与发布 |
| 维护者/交接负责人 | [交付修改清单](docs/HANDOVER_CHANGE_CHECKLIST.md)、[发布清单](docs/RELEASE_CHECKLIST.md) | PR/CI/审核、版本与包对应、验收记录、维护责任 |

学校需提供服务器及运维联系人、域名与证书、PostgreSQL/持久化存储、小程序管理员权限、AppSecret与模板，并指定业务和隐私负责人。根配置已有 AppID `wx78c441ce72d765fc`，仍需核验主体与成员权限；真实密钥通过学校受控渠道注入后端。

## 当前具备的功能

- 自习、开会、大型活动、音乐练习四场景自动分房；角色、容量、共享/独占和跨场景物理冲突在后端事务中复核。
- 默认半小时粒度、每日累计4小时；已完成预约仍计入当天额度，取消/驳回不计入。运行参数与分房规则可在管理页修改。
- 玉兰卡上传、人工/批量/自动审核、取消、签到/扫码签到、清扫上传与通过/退回；未上传和退回会阻断新申请，上传成功后先解除阻断。
- 违约记录和临时/限时/永久限制、明确起止时间的区间禁约；不设信用分。
- 管理员全部订单、违规与清扫待办、用户搜索、操作日志、筛选 Excel、鉴权照片链接和房间签到码。
- 人工核验后签发30分钟一次性恢复凭证；重发/使用使旧凭证失效，成功改密撤销旧会话，人工恢复还撤销微信绑定。辅导员随机初始密码、首次强制换密；正式管理员由受控 CLI 创建。
- 消息记录与发送状态、微信绑定/订阅授权/outbox；真实微信发送仍待学校配置和联调。
- PostgreSQL迁移、独立worker/readiness、公开/私密照片持久化、完整构建摘要、受控基础数据初始化与加密备份恢复工具。

学生注册成功即是启用的普通账号，**不等于学校身份已认证**；当前没有可信注册平台或短信找回服务。会议容量、申请前预览和冰箱使用等需求歧义待学校确认。实现与验证边界见 [需求对照](docs/REQUIREMENTS_TRACEABILITY.md)、[架构](docs/ARCHITECTURE.md) 和 [路线图](ROADMAP.md)。

## 本地演示启动

需要 Python 3.12+、Node.js 22（测试/构建）、微信开发者工具。本地用 SQLite；生产用 PostgreSQL 16，按 [部署教程](docs/DEPLOYMENT_GUIDE.md) 操作。Docker 是部署选项，直接运行 Python 的路径同样提供。

以下首次演示命令从**仓库根目录**执行。已有 `backend/.env` 时保留并检查，不覆盖；示例模板仅用于首次配置，设 `APP_ENV=development`。`seed.py` 会创建演示账号，禁止在学校生产库执行。

macOS/Linux：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
# 仅没有backend/.env时复制
cp -n backend/.env.example backend/.env
cd backend
../.venv/bin/python seed.py
../.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if (-not (Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
Set-Location backend
..\.venv\Scripts\python.exe seed.py
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

另开终端，从仓库根目录进入 `backend/`，macOS/Linux执行 `../.venv/bin/python -m app.worker`；Windows执行 `..\.venv\Scripts\python.exe -m app.worker`。worker负责自动审批、状态推进、通知和清理，API是独立进程。

模拟器导入仓库根目录，开发阶段临时关闭合法域名校验；默认API为 `http://127.0.0.1:8000/api`。访问 `http://127.0.0.1:8000/docs` 可查看本地接口。`admin001 / admin123` **仅用于虚构数据演示**。学校正式账号通过 `create_admin.py` 交互建号，账号存在时拒绝覆盖/提升权限；不要修改seed冒充正式建号。

`npm run build:dev` 默认沿用根 AppID。正式构建须显式提供 AppID、HTTPS API、版本和完整提交编号，并校验64个当前产物文件的摘要（数量随源码变化）；命令见 [构建教程](docs/BUILD_ARTIFACT_GUIDE.md)，无需手改 `config.js`。

## 测试与证据

从仓库根目录执行：

```sh
npm test
npm run release:check
cd backend
../.venv/bin/python -m pytest -q
# Windows后端命令：..\.venv\Scripts\python.exe -m pytest -q
```

后端测试使用每进程独立临时SQLite/上传目录，不修改现有演示库。2026-10-02，01–02轮后端 **48通过/2跳过**；03–04轮Node **30通过**。本轮05–11实际运行结果见 [教程与恢复验证报告](docs/HANDOVER_DOCUMENTATION_REPORT.md)，不将历史测试数字当作本轮新结果。两项普通pytest跳过项属于PostgreSQL并发作业；01–02临时PostgreSQL初始化演练与它们是不同验证。

本地恢复演练、教程命令核对和模拟器测试不能代替学校运维独立操作、iPhone/Android、真实HTTPS/微信消息以及签字验收。完整验收清单放在 [发布清单](docs/RELEASE_CHECKLIST.md) 和 [微信联调](docs/WECHAT_SETUP.md)，首页不重复列全部检查项。截图状态见 [截图说明](docs/assets/screenshots/README.md)，仅接受真实脱敏页面证据。

GitHub质量工作流由PR、main推送和`v*`版本标签触发；partner普通推送不会自动运行。每次交付合并按以下顺序执行：

1. 提交并推送 partner 的变更，建立 **partner → main** PR；后续修复继续推送该分支。
2. 在 PR 的 Checks / Actions 中确认最新目标提交的 `Backend tests`、`Miniprogram build policy`、`PostgreSQL concurrency`、`Dependency audit` 全部成功。后端作业也检查交付文档链接；普通 pytest 的两项 PG 跳过由独立 PostgreSQL 作业实际执行。
3. 等待仓库维护者审核；涉及工作流、部署、数据库或发布的变更须仓库所有者审核。新提交后重新核对检查与审批，不使用旧提交的成功结果。
4. 评审意见解决且检查成功后合入 main，核对 main 包含目标提交并检查 main 推送触发的结果；之后才进入第13–14项发布规则与打包。

`Miniprogram release artifact` 只在版本标签运行，PR 中显示 skipped 是预期行为，不代表正式构建已通过。PR 工作流通常在 GitHub 临时合并提交运行，应同时保存 PR head SHA 和工作流测试 SHA。远程 CI、审批和合并的实际证据保存到对应 PR，入口和本地预检记录见 [main 合并说明](docs/MAIN_INTEGRATION_REPORT.md)，审核要求见 [贡献指南](CONTRIBUTING.md)。

## 学校首次部署顺序

按 [部署教程](docs/DEPLOYMENT_GUIDE.md) 取得固定提交，配置学校环境 → PostgreSQL空库 → `alembic upgrade head`（目标`20261002_03`）→ `init_reference_data.py`补12房间/10规则 → `create_admin.py`正式建号 → API和独立worker → readiness → HTTPS → 构建/微信体验版 → 联合验收。

Compose从根`.env`或显式`--env-file`插值，不会自动读取`backend/.env`。直接Python从`backend/`读取后者。公开留言图与私密玉兰卡/清扫图分别持久化；私密图仅管理员鉴权读取并留审计，默认90天清理。导出照片链接不会绕过管理员登录。备份包含数据库和两个媒体目录，恢复与迁移目标必须一致。

## 源码、数据与协作

目录和文件用途见 [文件指南](docs/PROJECT_FILE_GUIDE.md)。使用虚构数据的演示见 [DEMO](docs/DEMO.md)，试点只记录汇总数据，见 [指标模板](docs/PILOT_METRICS.md)。

真实辅导员CSV、初始密码、数据库、照片、`.env`、备份解密密钥均不得进入Git/源码包。仓库提供 `Sheet_20250907.example.csv` 虚构模板；授权导入和凭据发放见 [运维手册](docs/OPERATIONS_RUNBOOK.md)。安全报告请按 [安全政策](SECURITY.md) 私下处理；协作与支持见 [贡献指南](CONTRIBUTING.md)、[支持说明](SUPPORT.md)。权利归属、许可证、后续维护期限和签字仍由学校及维护者确认。
