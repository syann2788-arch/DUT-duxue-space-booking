# 笃学书院空间预约系统 v2

面向大连理工大学笃学书院的原生微信小程序 + FastAPI 预约系统。v2 以第一版 `miniprogram/` 的紫色界面、空间导览和交互为产品基线，将数据层从微信云函数升级为可交接学校服务器的 FastAPI。默认用 SQLite 本地演示，学校接手时通过环境变量切换 PostgreSQL。

> 当前定位：`v0.x` 校内试点候选，不是已达到生产标准的通用开源预约产品。评审问题、修复证据与外部阻断项见 [评审整改台账](docs/REVIEW_REMEDIATION.md)。

## 问题、方案与价值

书院原有群聊/表格排房难以同时处理共享容量、独占活动、辅导员专属空间和跨房间冲突。本系统把规则集中在后端事务中：学生按场景和连续时段提交，系统给出候选空间，管理员审核，使用结束后通过清扫复核闭环。它与通用日历工具的区别是“规则驱动的自动分房 + 角色权限 + 清扫/限制闭环”，而非只保存一个时间段。

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
- 时段、时长、自动审批时间、提醒时间、房间优先级/容量/共享方式后台配置
- 微信账号绑定、订阅消息授权与可靠消息队列
- 实际使用者空间留言板，支持文字、照片和隐私字段最小化
- SQLite 历史表兼容升级、PostgreSQL/Docker/nginx 部署模板

详细设计见 [系统架构](docs/ARCHITECTURE.md)，老师需求逐条验收见 [需求对照表](docs/REQUIREMENTS_TRACEABILITY.md)，需要你配合的微信平台步骤见 [微信联调清单](docs/WECHAT_SETUP.md)。

## 本地启动（Windows）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
Copy-Item backend\.env.example backend\.env
$env:BOOTSTRAP_ADMIN_STUDENT_ID="demo-admin"
$env:BOOTSTRAP_ADMIN_PASSWORD="请替换为至少12位随机演示密码"
Set-Location backend
..\.venv\Scripts\python.exe seed.py
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

访问 Swagger：`http://localhost:8000/docs`。种子脚本不会再创建固定管理员；只有同时设置 `BOOTSTRAP_ADMIN_STUDENT_ID` 和 `BOOTSTRAP_ADMIN_PASSWORD` 时才会一次性初始化演示管理员。请勿把真实学号、手机号或密码写入仓库。

微信开发者工具直接导入本仓库根目录，它会根据 `project.config.json` 加载 `miniprogram/`。本地模拟器默认请求 `http://127.0.0.1:8000/api`。无需手改源码：`npm.cmd --prefix miniprogram run build:dev` 会生成 `dist/wechat/` 开发产物；staging/production 构建通过环境变量注入 HTTPS API 和 AppID，并拒绝本地、HTTP、占位域名或空 AppID。

## 测试

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q --cov=app --cov-report=term-missing --cov-fail-under=60
Set-Location ..\miniprogram
npm.cmd ci
npm.cmd run check
```

每个 pytest 进程使用自己的临时数据库与上传目录，不会修改 `backend/shuyuan.db`，也不会与并发测试互相删除文件。GitHub Actions 会在 PR 和 `main` 上重复执行后端、小程序和容器门禁。

## 目录说明

- `backend/app/`：唯一业务后端和全部一致性规则
- `miniprogram/`：正式原生微信小程序（v1 产品体验基础上的 v2 主线）
- `frontend/`：此前的 uni-app 实验实现，仅作页面和业务逻辑参考
- `backend/tests/`：HTTP 级业务回归
- `deploy/`：学校服务器 nginx 模板
- `cloudfunctions/`：第一版历史参考；`project.config.json` 已关闭云开发，不能作为 v2 部署入口

## 生产部署

1. 设置 `ENVIRONMENT=production`、PostgreSQL `DATABASE_URL`、至少 32 字符的随机 `SECRET_KEY`，并保持 `ALLOW_OPEN_REGISTRATION=false`。不安全配置会拒绝启动。
2. 后端运行 `python seed.py` 后，以单 worker 启动（内置定时器要求单 worker）。如学校使用多实例，应关闭 `ENABLE_SCHEDULER`，改由一个独立任务实例或 cron 调用任务。
3. nginx 配置 HTTPS，把 `/api/` 和 `/uploads/` 代理至 FastAPI；示例见 `deploy/nginx.conf`。
4. 使用 `MINIPROGRAM_API_BASE_URL=https://学校域名/api` 和 `MINIPROGRAM_APP_ID=...` 执行 `npm.cmd --prefix miniprogram run build:production`，导入 `dist/wechat/`，无需修改源码。
5. 按 [微信联调清单](docs/WECHAT_SETUP.md) 填写 AppID、AppSecret、订阅模板和合法域名。

照片当前存储在 `UPLOAD_DIR`。正式环境应挂载持久化磁盘；如果学校已有对象存储，可只替换上传服务，业务表继续保存 URL。

## 辅导员数据安全

真实的 `Sheet_20250907.csv` 可能包含姓名、班级和联系方式，已通过 `.gitignore` 排除，不应上传到公开仓库。仓库只提供虚构数据模板 `Sheet_20250907.example.csv`。本地导入时复制并重命名模板，再填入经授权的数据；也可通过环境变量 `COUNSELOR_CSV_PATH` 指定文件路径。
