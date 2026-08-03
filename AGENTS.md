# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 项目概述

大连理工大学笃学书院（西山7舍）空间预约系统。支持师生预约书院空间，包含Web(H5)和微信小程序端。

## 技术栈

- **后端**: FastAPI (Python 3.12+) + SQLAlchemy 2.0 async + PostgreSQL + JWT认证
- **前端**: uni-app (Vue 3 Composition API + Pinia)，一套代码编译H5/微信小程序
- **部署**: 校内服务器 nginx + docker

## 启动命令

```bash
# 后端
cd backend
pip install -r requirements.txt
python seed.py              # 初始化房间 + 管理员(admin001/admin123)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端 (HBuilderX 打开 frontend/ 目录，或命令行)
cd frontend
npm run dev:h5              # H5网页开发
# 修改 api/index.js 中的 BASE_URL 指向后端地址
```

FastAPI 自带 Swagger 文档: `http://localhost:8000/docs`

## 架构

```
backend/app/
├── main.py          # FastAPI入口，CORS，路由注册
├── config.py        # 所有可调参数(开放时间、预约上限、违约阈值等)
├── database.py      # 异步SQLAlchemy引擎
├── models.py        # User, Room, Reservation, Violation 四张表
├── schemas.py       # Pydantic v2 请求/响应模型
├── auth.py          # JWT + bcrypt，get_current_user / require_admin
├── services.py      # 全部业务逻辑(查询/校验/预约/违约)
└── routers/
    ├── auth.py      # POST /register, /login, GET /me
    ├── rooms.py     # GET 房间列表/详情/时段可用性
    ├── reservations.py  # POST 预约/取消/签到, GET 我的预约
    └── admin.py     # 用户管理/辅导员CSV导入/公开空间状态
```

**关键设计决策**:
- 所有时间校验(取消截止、签到宽限)在 `services.py` 内完成，与DB操作在同一事务中，不在router层
- 违约检测由 `refresh_reservation_states()` 与后台分钟任务共同触发，并以预约号+违约类型保证幂等
- JWT payload: `{"sub": user_id_str, "student_id": str, "role": str}`; router层通过 `int(user["sub"])` 获取user_id
- 前端Pinia store (`store/user.js`) 管理登录态，token存uni.storage，API层自动附加Authorization头

## 业务规则 (config.py)

| 参数 | 值 | 说明 |
|------|-----|------|
| OPEN_HOUR / CLOSE_HOUR | 8 / 22 | 每天14个时段 |
| MAX_HOURS_PER_DAY | 4 | 每人每天上限 |
| ADVANCE_DAYS | 1 | 提前1天预约 |
| CHECKIN_GRACE_MINUTES | 15 | 开始后15分钟签到 |
| CANCEL_DEADLINE_MINUTES | 30 | 开始前30分钟可取消 |
| VIOLATION_THRESHOLD | 3 | 累计3次违约 |
| VIOLATION_BAN_DAYS | 30 | 每累计3次有效违约自动禁约30天 |

## 房间配置

| 房间 | 预约规则 |
|------|---------|
| A101日新阁 | 学生可预约 |
| A102格物居 | 公开，管理员标状态(free/busy/crowded) |
| A103致知堂 | 学生可预约(最大空间) |
| A104悠然亭 | 公开，管理员标状态(有冰箱) |
| A105聚思轩 | 学生可预约 |
| A106汇心驿 | 仅辅导员预约(who_can_reserve=counselor) |
| B102韵音阁 | 学生可预约(有乐器) |
| B101/C101-C104 | 仅展示，不可互动 |

## 辅导员导入

CSV格式(Sheet_20250907.csv): 职务,姓名,负责班级,联系方式,...
- 后端自动检测CSV格式（简单学号列表 vs 完整员工信息表）
- 导入脚本: `python import_counselors.py`
- Web端: 管理后台 → 辅导员管理 → 上传CSV

## 已知限制

- 预约并发检查非原子性(MVP阶段)，高并发下可能重复预约同一时段
- `check_missed_checkins`在热路径上执行，用户量增大后应改为cron任务
- 无分页，所有列表接口全量返回
