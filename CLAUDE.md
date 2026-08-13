# CLAUDE.md

## 项目背景

大连理工大学笃学书院（西山7舍）空间预约系统。当前主线为 uni-app 微信小程序/H5 + FastAPI；不设信用分，采用可审计违约记录与预约限制。

## 不可破坏的业务红线

1. 玉兰卡照片（私密 `media_id`）、手机号、学号属个人隐私，仅管理员可见；列表/导出接口须按角色白名单脱敏，新字段默认不可见。
2. 违约记录是审计数据，只增不改不删；幂等键为 `(reservation_id, type)`（见 `models.py` 的 `uq_violation_reservation_type` 唯一约束）。
3. 微信 `AppSecret` 永不下发前端/小程序；`code2session` 仅在服务端 `backend/app/routers/auth.py::_code2session` 调用。
4. 预约并发靠数据库行锁（`SELECT ... WITH FOR UPDATE`）+ 锁内复检，不能靠"先查后写"。

## 硬性技术约定（后端）

- 状态机：`ReservationStatus` 等领域枚举只在 `app/models.py` 定义；`OCCUPYING_STATUSES` / `DAILY_LIMIT_STATUSES`（"哪些状态占用时段/计入单日上限"）只在 `app/services.py` 定义。【守护: backend/guards/test_conventions.py】
- 时区：业务逻辑的"现在"一律用 `app/models.py::local_now()`（Asia/Shanghai naive，与 `date + slot` 表示一致）；`services.py` 禁用裸 `datetime.now()`。【守护: backend/guards/test_conventions.py】
- 数据流：时间校验（取消截止、签到宽限、违约判定）在 `services.py` 内与 DB 操作同事务完成，`routers/` 不导入 `timedelta`。【守护: backend/guards/test_conventions.py】
- 并发：分房前 `SELECT Room.id ... WITH FOR UPDATE ORDER BY Room.id` 锁物理房间，`_candidate_available` 在锁内复检；状态流转用 `status.in_(...)` 条件更新。
- 幂等：违约用 `(reservation_id, type)` 唯一约束；限制到期靠 `ends_at` 判定，`_active_restriction` 顺带回收。

## 技术栈

正式 v2 运行链路只有一个前端主线：原生微信小程序 `miniprogram/`。其余前端目录的定位如下：

| 目录 | 当前定位 | 是否属于正式 v2 运行链路 |
|---|---|---|
| `miniprogram/` | 原生微信小程序，正式交付前端 | 是 |
| `frontend/` | 此前的 uni-app/H5 实验实现，供页面和业务逻辑参考 | 否 |
| `cloudfunctions/` | 第一版微信云函数参考代码 | 否 |
| `../dut-duxue-space-booking-showcase.design/` | 橙紫视觉规范唯一源（HTML 静态原型） | 视觉规范，非运行代码 |

- **前端**: 原生微信小程序 (`miniprogram/`)，紫色主题，自定义 tabBar
- **后端**: FastAPI（Python 3.12+）+ SQLAlchemy async + JWT 认证
- **数据库**: SQLite 本地演示 / PostgreSQL 生产

### 视觉规范唯一源

`dut-duxue-space-booking-showcase.design/` 是视觉规范的唯一源，`miniprogram/` 的色值须以此为准对齐：

| 角色 | 色值 | 用途 |
|---|---|---|
| 品牌主色（暖橙） | `#F25B15` | 主按钮、FAB、选中态、CTA、导航选中 |
| 辅助品牌色（紫） | `#6B46C1` | 渐变紫端、信息分类点、链接文字 |
| 状态语义色 | 绿/红/棕/蓝 | 成功/danger/cleanup/info，不参与品牌色替换 |

注：`miniprogram/` 当前仍为旧紫 `#6b2d8e`，对齐到橙紫是独立迭代（见已知待办）。【守护: backend/guards/test_conventions.py】

## 启动方式

1. 后端：`cd backend` → `python seed.py` → `uvicorn app.main:app --reload`
2. 微信小程序：微信开发者工具导入仓库根目录（`project.config.json` 的 `miniprogramRoot: "miniprogram/"` 加载正式前端）
3. 本地开发 API 默认：`http://127.0.0.1:8000/api`；真机预览前需在 `miniprogram/config.js` 配置手机可访问的 HTTPS 地址

管理员: admin001 / admin123

## 核心业务规则

| 参数 | 值 | 说明 |
|------|-----|------|
| 开放时间 | 8:00-22:00 | 30分钟/时段，共28个时段 |
| 单次最大 | 8时段(4小时) | start_slot / end_slot 为时段索引 |
| 提前预约 | 7天 | 后台可改 |
| 签到宽限 | 开始后15分钟 | |
| 取消截止 | 开始前30分钟 | |
| 违约阈值 | 3次 | |
| 自动禁约 | 每累计3次违约禁约30天 | 后台可改 |

## 房间配置

可预约: A101日新阁, A102格物居, A103致知堂, A105聚思轩, B102韵音阁
辅导员专属: A106汇心驿 (who_can_reserve=counselor)
公开空间(管理员标状态): A102格物居, A104悠然亭
不可互动(仅展示): B101, C101-C104

## 关键设计要点

- **日期比较**: 所有日期用 ISO 字符串 `YYYY-MM-DD` 比较，北京时区用 `Date.now() + 8*3600000` 计算
- **Token 认证**: JWT 存 `wx.storage`，`miniprogram/utils/api.js` 统一附加 `Authorization: Bearer <token>`；401 仅在响应对应 token 仍是当前 token 时清除登录态，避免冷启动并发请求误删新会话
- **微信订阅消息**: 后端 `app/notifications.py` outbox + 分钟任务投递；模板 ID 在 `system_settings` / `settings` 配置，一次性订阅
- **统一请求入口**: `miniprogram/utils/api.js` 的 `request` / `uploadFile`，自动附加 JWT 并把 FastAPI 错误结构转成可展示文本
- **自定义 tabBar**: `miniprogram/custom-tab-bar/`，`app.json` 里 `"custom": true`
- **时间轴渲染**: 按 segments 块级合并同人连续预约，不同人间 3rpx 缝隙
- **时段格式**: slot 索引 0-27，对应 8:00-22:00，每 slot 30 分钟
- **业务安全**: 不依赖前端按钮是否显示，后端必须始终执行最终校验

## 已知待办

- SMS 模板 ID 仍是占位符 `YOUR_SMS_TEMPLATE_ID`
- `reservations` 表需要 `created_at` 降序索引（非唯一）
- 签到二维码需外部生成（管理后台可复制 JSON），永久有效
- 预约并发：SQLite 本地演示无 PostgreSQL 等价的 `WITH FOR UPDATE` 行锁语义，生产必须使用 PostgreSQL；行锁 + 锁内复检的并发模式见上方业务红线 #4
- `miniprogram/` 已从旧紫 `#6b2d8e` 迁移到橙紫（橙 `#F25B15` + 紫 `#6B46C1`），色值变量集中在 `app.wxss`，旧紫复现由守护拦截【守护: backend/guards/test_conventions.py】

## 工作约定

- 后端业务逻辑只写在 `backend/app/services.py`；`routers/` 只做参数解析、认证转发与 HTTP 错误翻译，不引入 `timedelta` 做时间运算【守护: backend/guards/test_conventions.py】
- 时间相关用 ISO 字符串比较，不要用 Date 对象直接比；后端用 `local_now()`
- UI 风格：`miniprogram/` 的色值须以 `dut-duxue-space-booking-showcase.design/` 为视觉规范唯一源（橙 `#F25B15` 主 + 紫 `#6B46C1` 辅），不得自行定义品牌色；状态语义色（成功绿/danger 红/cleanup 棕/info 蓝）保留不动
- `miniprogram/` 是唯一前端主线；改 `frontend/`(uni-app) 或 `cloudfunctions/`(v1) 前须先与用户确认，不得默认它们是交付物

## 守护测试（eng-vibe 第 2 步）

约定必须机器可执行。`backend/guards/test_conventions.py` 用 AST 扫描源码，断言上方【守护】标注的约定成立，<1s 完成、不连 DB。每次改后端后跑：

```bash
cd backend && python -m pytest guards/ -q
```

故意违反任一条都会红，并报出 `文件:行号`。新增昂贵约定（状态机、权限边界、幂等键）时，先补一条守护测试，再写代码。`eng-vibe.config.json` 已把该命令注册为守护闸门。
