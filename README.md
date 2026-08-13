# 笃学书院空间预约系统 v2

面向大连理工大学笃学书院的原生微信小程序 + FastAPI 预约系统。v2 以第一版 `miniprogram/` 的空间导览和交互骨架为产品基线，采用暖橙 `#F25B15` + 紫色 `#6B46C1` 的正式视觉，将数据层从微信云函数升级为可交接学校服务器的 FastAPI。默认用 SQLite 本地演示，学校接手时通过环境变量切换 PostgreSQL。

当前版本标识为 `0.1.0-rc.1` 候选准备稿，尚未创建 GitHub Release，也没有通过生产验收。

## 解决什么问题

群聊或表格登记难以同时处理空间权限、人数容量、共享/独占、跨场景物理冲突、签到和清扫闭环。本系统把这些规则放到同一个后端事务中：学生按使用场景和连续时段提交，服务器自动选择合适空间；管理员只处理审核和例外，不需要手工反复比对房间表。

- 对学生：统一查看空间、可用时段、审核、签到和清扫状态。
- 对辅导员：隔离 A106 等角色专属空间权限。
- 对管理员：集中审核、清扫复核、限制、配置和脱敏数据导出。
- 对运维：提供 PostgreSQL、迁移、独立 worker、健康检查、备份恢复和可重复构建路径。

## 产品演示

正式前端是 `miniprogram/`，不是 `frontend/`。使用虚构数据的 15 分钟完整流程见 [匿名演示与验收](docs/DEMO.md)，首轮试点只记录汇总指标，见 [试点指标模板](docs/PILOT_METRICS.md)。

候选版真实截图尚待脱敏真机验收后补入 `docs/assets/screenshots/`；在此之前不会用设计稿、旧页面或 AI 图片冒充产品证据。

## 已实现

- 自习、开会、大型活动、音乐练习四场景自动分房
- A106 仅辅导员可预约，学生端和后端分房均执行角色隔离
- 30 分钟预约粒度、单日累计 4 小时（后台可改）
- 共享容量/独占冲突校验；B102 音乐练习独立，A103 钢琴时段与大型活动互斥
- 待审核、管理员单条/批量审核、每日 23:00 自动审批
- 玉兰卡照片必传；结束后上传清扫照片即解锁，后台异步复核
- 不设信用分；每累计 3 次有效违约自动禁约 30 天
- 临时/限时/永久预约限制
- 预约数据 Excel 导出
- 历史预约、审核、清扫和用户列表服务端分页及失败重试
- 时段、时长、自动审批时间、提醒时间、房间优先级/容量/共享方式后台配置
- 微信账号绑定、订阅消息授权与可靠消息队列
- 实际使用者空间留言板，支持文字、照片和隐私字段最小化
- SQLite 历史表兼容升级、PostgreSQL/Docker/nginx 部署模板

详细设计见 [系统架构](docs/ARCHITECTURE.md)，老师需求逐条验收见 [需求对照表](docs/REQUIREMENTS_TRACEABILITY.md)，需要你配合的微信平台步骤见 [微信联调清单](docs/WECHAT_SETUP.md)。参与修改前请阅读 [贡献指南](CONTRIBUTING.md) 和 [支持说明](SUPPORT.md)。

当前项目仍处于校内试点准备阶段，不代表已经通过生产安全验收。当前状态和阻断项以 [ROADMAP](ROADMAP.md) 为准，发布门槛见 [校内试点发布基线](docs/PILOT_RELEASE_BASELINE.md)，变更记录见 [CHANGELOG](CHANGELOG.md)，安全问题请按 [安全政策](SECURITY.md) 私下报告。

## 本地启动（Windows）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
Set-Location backend
..\.venv\Scripts\python.exe seed.py
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

如需验证 23:00 自动审批、状态推进、通知和媒体到期清理，请另开一个终端运行：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m app.worker
```

API 与 worker 是两个独立进程；只测试页面和手工接口时可以暂不启动 worker。

访问 Swagger：`http://localhost:8000/docs`。演示管理员为 `admin001 / admin123`，首次登录后应立刻改成学校内部安全账号（当前版本可直接在数据库初始化脚本中替换）。

微信开发者工具直接导入本仓库根目录，它会根据 `project.config.json` 加载 `miniprogram/`。本地模拟器默认请求 `http://127.0.0.1:8000/api`，需在“本地设置”中关闭合法域名校验。真机/生产产物通过 `npm run build:staging` 或 `npm run build:prod` 注入手机可访问的 HTTPS 后端，无需手工修改源码。

## 测试

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
```

小程序纯业务逻辑与构建门禁：

```powershell
npm test
npm run release:check
```

后端测试使用隔离临时目录，不会修改现有 `backend/shuyuan.db`。GitHub Actions 会同时运行后端、PostgreSQL 并发和小程序逻辑/构建检查。

### 当前尚未完成的测试

本地自动检查当前结果为：后端 `34 passed, 1 skipped`，小程序逻辑、构建和发布规则检查全部通过。跳过项是本机没有 PostgreSQL 测试环境，不代表 PostgreSQL 已在本机完成验收。以下检查完成前，项目状态仍是“本地候选准备完成，尚未通过校内试点和生产验收”。

#### 1. 真实手机验收

- [ ] iPhone 完成注册、登录、空间导览、预约、审核结果、签到、清扫和退出主流程。
- [ ] 安卓手机完成同一套主流程。
- [ ] 验证“我的”、管理后台和长列表可以滚动，底部按钮不被安全区域或键盘遮挡。
- [ ] 验证图片选择、玉兰卡/清扫照片上传、失败重试和预览。
- [ ] 验证筛选 Excel 下载/打开、签到二维码生成/保存和扫码签到。
- [ ] 在 Wi-Fi、移动网络和弱网下验证超时提示、分页续载和重复点击不会产生重复预约。
- [ ] 后端短暂中断并恢复后，验证登录态、页面重试和业务状态可以恢复。
- [ ] 使用 VoiceOver 或安卓读屏检查关键按钮、表单和状态提示。

#### 2. PostgreSQL 与生产等价环境

- [ ] 在 PostgreSQL 16 上从空库执行 `alembic upgrade head`，确认 revision 为 `20260813_02`。
- [ ] 用并发请求验证同一房间、同一时段不会超容量或重复占用。
- [ ] 启动多个 API 实例和独立 worker，验证状态推进、自动审批和通知任务不会重复执行。
- [ ] 验证 `/api/ready`、worker 心跳、消息 outbox、告警和优雅停止。
- [ ] 完成数据库与私密媒体的备份、校验、空环境恢复和应用回滚演练。
- [ ] 使用接近试点规模的数据检查预约列表、状态推进、管理筛选和 Excel 导出的性能。

#### 3. 微信平台联调

- [ ] 配置正式或试点 AppID、AppSecret、HTTPS API、合法域名和隐私保护指引。
- [ ] 验证微信登录、已有账号绑定，以及无配置或绑定失败时的可理解提示。
- [ ] 验证预约提交、审核结果、开始提醒和限制通知四类订阅消息的成功路径。
- [ ] 验证微信接口超时或失败不会回滚已经成功的预约、审核或限制操作。
- [ ] 上传体验版并使用受邀测试账号完成一次端到端验收。

#### 4. 发布证据与试点验收

- [ ] 从当前正式 `miniprogram/` 脱敏截取 `student-space-guide.png`、`student-my-reservations.png` 和 `admin-review.png`，不得使用设计稿或生成图替代。
- [ ] 按 [匿名演示与验收](docs/DEMO.md) 完成学生、辅导员和管理员流程并记录问题。
- [ ] 填写 [试点指标模板](docs/PILOT_METRICS.md)，只保留汇总数据和脱敏证据。
- [ ] 由仓库维护者、书院业务负责人、学校运维、小程序管理员和隐私责任人完成发布清单签字。
- [ ] 在干净工作区执行 `npm run release:check -- --tag` 并通过全部标签前门禁。

校内身份可信注册和默认管理员凭据替换是已知发布阻断项，目前按项目决定暂缓，不应因为上述测试通过而被标记为已解决。完整责任边界见 [项目路线图](ROADMAP.md) 和 [候选版发布清单](docs/RELEASE_CHECKLIST.md)。

## 目录说明

- `backend/app/`：唯一业务后端和全部一致性规则
- `miniprogram/`：正式原生微信小程序（v1 产品体验基础上的 v2 主线）
- `frontend/`：此前的 uni-app 实验实现，仅作页面和业务逻辑参考
- `backend/tests/`：HTTP 级业务回归
- `deploy/`：学校服务器 nginx 模板
- `cloudfunctions/`：第一版微信云函数参考；v2 主数据源为 FastAPI

## 生产部署

1. 将 `DATABASE_URL` 改为 `postgresql+asyncpg://...`，设置 `APP_ENV=production` 和强随机 `SECRET_KEY`。
2. 先执行 `alembic upgrade head`，再分别启动 API 与 `python -m app.worker`；API 不再隐式建表或运行定时任务。
3. nginx 配置 HTTPS，把 `/api/` 和公开留言图片的 `/uploads/` 代理至 FastAPI；示例见 `deploy/nginx.conf`。
4. 使用 `MINIPROGRAM_API_BASE_URL`、`MINIPROGRAM_APP_ID`、`RELEASE_VERSION` 和 `GIT_COMMIT` 执行 `npm run build:prod`；生产门禁会拒绝 HTTP、本地/局域网地址、空或无效 AppID。
5. 访问 `/api/ready` 验证数据库 revision、worker 心跳和 outbox，再按 [微信联调清单](docs/WECHAT_SETUP.md) 完成真机验收。

完整发布、回滚、备份恢复和事故处理见 [生产运行手册](docs/OPERATIONS_RUNBOOK.md)。本地开发仍直接使用源码中的 `http://127.0.0.1:8000/api`，无需手工改动。

留言图片存储在 `UPLOAD_DIR` 并通过受限的 `/uploads/message_*` 路由公开；玉兰卡和清扫照片存储在 `PRIVATE_UPLOAD_DIR`，业务只保存 `media_id`，仅管理员可鉴权下载且访问会记录审计日志。敏感媒体默认保留 90 天，由后台任务到期删除；正式环境应为两个目录配置独立的持久化存储或替换为校内对象存储。

## 辅导员数据安全

真实的 `Sheet_20250907.csv` 可能包含姓名、班级和联系方式，已通过 `.gitignore` 排除，不应上传到公开仓库。仓库只提供虚构数据模板 `Sheet_20250907.example.csv`。本地导入时复制并重命名模板，再填入经授权的数据；也可通过环境变量 `COUNSELOR_CSV_PATH` 指定文件路径。
