# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## 项目概述

大连理工大学笃学书院（西山7舍）空间预约系统。支持师生预约书院空间。

## 前端主线（务必先读）

- `miniprogram/` 是第一版原生微信小程序延续下来的正式产品主线，第二版必须在它的紫色视觉、空间导览和交互骨架上升级。
- 微信开发者工具导入仓库根目录；根目录 `project.config.json` 的 `miniprogramRoot` 必须保持为 `miniprogram/`。
- `frontend/` 是此前另行实现的 uni-app/H5 方案，仅作业务逻辑和管理页面参考，除非用户明确要求，不得把它当成最终微信端，也不得把 `miniprogram/` 标为废弃。
- `cloudfunctions/` 是第一版微信云开发后端参考。第二版原生前端通过 `miniprogram/utils/api.js` 接入 FastAPI，不再以云函数作为主数据源。

## 技术栈

- **后端**: FastAPI (Python 3.12+) + SQLAlchemy 2.0 async + PostgreSQL + JWT认证
- **微信前端主线**: 原生微信小程序 (`miniprogram/`)，紫色主题
- **参考前端**: uni-app (`frontend/`)，目前不是微信端交付主线
- **部署**: 校内服务器 nginx + docker

## 启动命令

```bash
# 后端
cd backend
pip install -r requirements.txt
python seed.py              # 初始化房间 + 管理员(admin001/admin123)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 微信小程序
# 微信开发者工具直接导入仓库根目录；本地开发 API 默认：
# http://127.0.0.1:8000/api
# 真机预览前需在 miniprogram/config.js 配置手机可访问的 HTTPS 地址
```

FastAPI 自带 Swagger 文档: `http://localhost:8000/docs`

## 架构

```
backend/app/
├── main.py          # FastAPI入口，CORS，路由注册
├── config.py        # 所有可调参数(开放时间、预约上限、违约阈值等)
├── database.py      # 异步SQLAlchemy引擎
├── models.py        # 用户、房间、预约、清扫、限制、配置、通知、违约等数据表
├── schemas.py       # Pydantic v2 请求/响应模型
├── auth.py          # JWT + bcrypt，get_current_user / require_admin
├── services.py      # 全部业务逻辑(查询/校验/预约/违约)
└── routers/
    ├── auth.py      # POST /register, /login, GET /me
    ├── rooms.py     # 房间列表/详情/时段、使用者留言与留言照片
    ├── reservations.py  # 场景可用性/预约/取消/签到/照片/清扫
    └── admin.py     # 审批/清扫复核/限制/配置/导出/辅导员
```

**关键设计决策**:
- 所有时间校验(取消截止、签到宽限)在 `services.py` 内完成，与DB操作在同一事务中，不在router层
- 违约检测由 `refresh_reservation_states()` 与后台分钟任务共同触发，并以预约号+违约类型保证幂等
- JWT payload: `{"sub": user_id_str, "student_id": str, "role": str}`; router层通过 `int(user["sub"])` 获取user_id
- 原生小程序 `miniprogram/app.js` 管理登录态，token 存 `wx.storage`，`miniprogram/utils/api.js` 自动附加 Authorization

## 业务规则 (config.py)

| 参数 | 值 | 说明 |
|------|-----|------|
| OPEN_HOUR / CLOSE_HOUR | 8 / 22 | 每天28个半小时时段 |
| MAX_HOURS_PER_DAY | 4 | 每人每天上限 |
| ADVANCE_DAYS | 7 | 可预约今天起7天内 |
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
- FastAPI 管理接口和原生小程序管理页均支持 CSV 导入

## 已知限制

- SQLite 本地开发无法提供 PostgreSQL 等价的行锁语义；生产必须使用 PostgreSQL
- 微信订阅消息必须在学校提供正式 AppID、AppSecret 和模板 ID 后才能真实发送
- 无分页，所有列表接口全量返回
