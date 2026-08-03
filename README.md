# 笃学书院空间预约系统 v2

面向大连理工大学笃学书院的 uni-app 微信小程序/H5 + FastAPI 预约系统。v2 已从历史微信云开发原型收敛为独立后端，默认可用 SQLite 本地演示，学校接手时通过环境变量切换 PostgreSQL。

## 已实现

- 自习、开会、大型活动、音乐练习四场景自动分房
- 30 分钟预约粒度、单日累计 4 小时（后台可改）
- 共享容量/独占冲突校验，A103 与 B102 互斥，大型活动优先
- 待审核、管理员单条/批量审核、每日 23:00 自动审批
- 签到、结束后清扫照片上传、后台复核、未完成复核禁止下一次预约
- 临时/限时/永久预约限制
- 预约数据 Excel 导出
- 时段、时长、自动审批时间、提醒时间、房间优先级/容量/共享方式后台配置
- 微信账号绑定、订阅消息授权与可靠消息队列
- SQLite 历史表兼容升级、PostgreSQL/Docker/nginx 部署模板

详细设计见 [系统架构](docs/ARCHITECTURE.md)，需要你配合的微信平台步骤见 [微信联调清单](docs/WECHAT_SETUP.md)。

## 本地启动（Windows）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
Set-Location backend
..\.venv\Scripts\python.exe seed.py
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

打开另一终端：

```powershell
Set-Location frontend
Copy-Item .env.example .env
npm.cmd install
npm.cmd run dev:h5
```

访问 Swagger：`http://localhost:8000/docs`。演示管理员为 `admin001 / admin123`，首次登录后应立刻改成学校内部安全账号（当前版本可直接在数据库初始化脚本中替换）。

也可用 HBuilderX 直接打开 `frontend/`。微信开发者工具导入命令行产物 `frontend/dist/build/mp-weixin/`；H5 产物位于 `frontend/dist/build/h5/`。

## 测试

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
```

测试使用独立 `test_pytest.db`，不会修改现有 `backend/shuyuan.db`。

## 目录说明

- `backend/app/`：唯一业务后端和全部一致性规则
- `frontend/`：uni-app 学生端与管理端，一套代码构建 H5/微信小程序
- `backend/tests/`：HTTP 级业务回归
- `deploy/`：学校服务器 nginx 模板
- `miniprogram/`、`cloudfunctions/`：历史微信云开发原型，仅保留参考，不再作为 v2 数据源

## 生产部署

1. 将 `DATABASE_URL` 改为 `postgresql+asyncpg://...`，设置强随机 `SECRET_KEY`。
2. 后端运行 `python seed.py` 后，以单 worker 启动（内置定时器要求单 worker）。如学校使用多实例，应关闭 `ENABLE_SCHEDULER`，改由一个独立任务实例或 cron 调用任务。
3. nginx 配置 HTTPS，把 `/api/` 和 `/uploads/` 代理至 FastAPI；示例见 `deploy/nginx.conf`。
4. 前端 `.env` 的 `VITE_API_BASE_URL` 改为学校 HTTPS API 域名后重新构建。
5. 按 [微信联调清单](docs/WECHAT_SETUP.md) 填写 AppID、AppSecret、订阅模板和合法域名。

照片当前存储在 `UPLOAD_DIR`。正式环境应挂载持久化磁盘；如果学校已有对象存储，可只替换上传服务，业务表继续保存 URL。

## 辅导员数据安全

真实的 `Sheet_20250907.csv` 可能包含姓名、班级和联系方式，已通过 `.gitignore` 排除，不应上传到公开仓库。仓库只提供虚构数据模板 `Sheet_20250907.example.csv`。本地导入时复制并重命名模板，再填入经授权的数据；也可通过环境变量 `COUNSELOR_CSV_PATH` 指定文件路径。
