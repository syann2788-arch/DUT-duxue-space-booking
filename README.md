# 笃学书院空间预约系统 v2

面向大连理工大学笃学书院的原生微信小程序 + FastAPI 预约系统。v2 以第一版 `miniprogram/` 的紫色界面、空间导览和交互为产品基线，将数据层从微信云函数升级为可交接学校服务器的 FastAPI。默认用 SQLite 本地演示，学校接手时通过环境变量切换 PostgreSQL。

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

当前项目仍处于校内试点准备阶段，不代表已经通过生产安全验收。发布门槛见 [校内试点发布基线](docs/PILOT_RELEASE_BASELINE.md)，变更记录见 [CHANGELOG](CHANGELOG.md)，安全问题请按 [安全政策](SECURITY.md) 私下报告。

## 本地启动（Windows）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
Set-Location backend
..\.venv\Scripts\python.exe seed.py
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

访问 Swagger：`http://localhost:8000/docs`。演示管理员为 `admin001 / admin123`，首次登录后应立刻改成学校内部安全账号（当前版本可直接在数据库初始化脚本中替换）。

微信开发者工具直接导入本仓库根目录，它会根据 `project.config.json` 加载 `miniprogram/`。本地模拟器默认请求 `http://127.0.0.1:8000/api`，需在“本地设置”中关闭合法域名校验。真机预览时必须把 `miniprogram/config.js` 的默认地址换成手机可访问的 HTTPS 后端。

## 测试

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
```

测试使用独立 `test_pytest.db`，不会修改现有 `backend/shuyuan.db`。

## 目录说明

- `backend/app/`：唯一业务后端和全部一致性规则
- `miniprogram/`：正式原生微信小程序（v1 产品体验基础上的 v2 主线）
- `frontend/`：此前的 uni-app 实验实现，仅作页面和业务逻辑参考
- `backend/tests/`：HTTP 级业务回归
- `deploy/`：学校服务器 nginx 模板
- `cloudfunctions/`：第一版微信云函数参考；v2 主数据源为 FastAPI

## 生产部署

1. 将 `DATABASE_URL` 改为 `postgresql+asyncpg://...`，设置强随机 `SECRET_KEY`。
2. 后端运行 `python seed.py` 后，以单 worker 启动（内置定时器要求单 worker）。如学校使用多实例，应关闭 `ENABLE_SCHEDULER`，改由一个独立任务实例或 cron 调用任务。
3. nginx 配置 HTTPS，把 `/api/` 和公开留言图片的 `/uploads/` 代理至 FastAPI；示例见 `deploy/nginx.conf`。
4. 将 `miniprogram/config.js` 的 API 地址改为学校 HTTPS API 域名，并在微信公众平台配置 request/upload/download 合法域名。
5. 按 [微信联调清单](docs/WECHAT_SETUP.md) 填写 AppID、AppSecret、订阅模板和合法域名。

留言图片存储在 `UPLOAD_DIR` 并通过受限的 `/uploads/message_*` 路由公开；玉兰卡和清扫照片存储在 `PRIVATE_UPLOAD_DIR`，业务只保存 `media_id`，仅管理员可鉴权下载且访问会记录审计日志。敏感媒体默认保留 90 天，由后台任务到期删除；正式环境应为两个目录配置独立的持久化存储或替换为校内对象存储。

## 辅导员数据安全

真实的 `Sheet_20250907.csv` 可能包含姓名、班级和联系方式，已通过 `.gitignore` 排除，不应上传到公开仓库。仓库只提供虚构数据模板 `Sheet_20250907.example.csv`。本地导入时复制并重命名模板，再填入经授权的数据；也可通过环境变量 `COUNSELOR_CSV_PATH` 指定文件路径。
