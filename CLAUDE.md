# CLAUDE.md

## 项目背景

大连理工大学笃学书院（西山7舍）空间预约系统。当前主线为 uni-app 微信小程序/H5 + FastAPI；不设信用分，采用可审计违约记录与预约限制。

## 技术栈

历史原生小程序/微信云函数仅保留参考，当前运行目录结构：

```
frontend/                  ← uni-app Vue 3，一套代码编译 H5/微信小程序
backend/                   ← FastAPI + SQLAlchemy async 业务后端
deploy/                    ← nginx 部署模板
miniprogram/ cloudfunctions/ ← 历史原型，不作为 v2 数据源
```

- **前端**: uni-app（Vue 3 + Pinia）
- **后端**: FastAPI（Python 3.12+）
- **数据库**: SQLite 本地演示 / PostgreSQL 生产

## 启动方式

1. 运行 `backend/seed.py` 并启动 FastAPI
2. 在 `frontend/` 执行 `npm run build:mp-weixin`
3. 微信开发者工具导入 `frontend/dist/build/mp-weixin/`

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
- **Token 认证**: session_token 存 users 集合，login 时生成，app.call 自动附加
- **cloud.openapi.subscribeMessage**: 模板ID `JCFEQMxQbFljZcjHgj_Nwg5pwS8HyzOcGMavkuzGEDg`，一次性订阅
- **`app.call(name, data)`**: 统一云函数调用，自动附加 token，拦截认证失败跳登录
- **自定义 tabBar**: `miniprogram/custom-tab-bar/`，app.json 里 `"custom": true`
- **时间轴渲染**: 按 segments 块级合并同人连续预约，不同人间 3rpx 缝隙
- **时段格式**: slot 索引 0-27，对应 8:00-22:00，每 slot 30 分钟

## 已知待办

- SMS 模板 ID 仍是占位符 `YOUR_SMS_TEMPLATE_ID`
- `reservations` 集合需要 `created_at` 降序索引（非唯一）
- 签到二维码需外部生成（管理后台可复制 JSON），永久有效
- 预约并发检查非原子性 (MVP)

## 工作约定

- 只改 `miniprogram/` 和 `cloudfunctions/`，不改 `backend/` 和 `frontend/`
- 云函数改完提醒用户部署
- 时间相关用 ISO 字符串比较，不要用 Date 对象直接比
- UI 风格：主题色 `#6b2d8e`，圆角卡片
