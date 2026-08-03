# CLAUDE.md

## 项目背景

大连理工大学笃学书院（西山7舍）空间预约系统 —— 微信小程序。支持师生预约书院空间，包含签到、留言板、信用分等功能。

## 技术栈

这是**微信云开发**项目，不是传统后端。目录结构：

```
project.config.json        ← 小程序项目配置 (miniprogramRoot + cloudfunctionRoot)
miniprogram/               ← 微信小程序前端（原生，不是 uni-app）
cloudfunctions/            ← 微信云函数（后端）
  ├── auth/                ← 登录/注册/微信自动登录/找回密码
  ├── rooms/               ← 房间列表/详情/时段查询/热力图
  ├── reservations/        ← 预约/取消/签到/违约检测/订阅消息
  ├── admin/               ← 用户管理/禁约/公开状态/仪表盘/CSV导出
  ├── messages/            ← 空间留言板（支持照片）
  └── seed/                ← 初始化房间和管理员
```

- **前端**: 微信小程序原生 (WXML + WXSS + JS)，不是 uni-app
- **后端**: 微信云函数 (Node.js)，不是 FastAPI
- **数据库**: 微信云数据库 (NoSQL，集合: users/rooms/reservations/violations/messages)
- **存储**: 微信云存储（留言板照片）
- **云环境**: cloud1 (ID: cloud1-d8ge57zw246b73480)

## 启动方式

1. 微信开发者工具打开项目根目录
2. 编译运行 miniprogram/
3. 云函数右键上传部署后，seed 运行一次

管理员: admin001 / admin123

## 核心业务规则

| 参数 | 值 | 说明 |
|------|-----|------|
| 开放时间 | 8:00-22:00 | 30分钟/时段，共28个时段 |
| 单次最大 | 8时段(4小时) | start_slot / end_slot 为时段索引 |
| 提前预约 | 1天 | 今天+明天 |
| 签到宽限 | 开始后15分钟 | |
| 取消截止 | 开始前30分钟 | |
| 违约阈值 | 3次 | |
| 禁约天数 | 7天 | |
| 信用分 | +1签到 +1留言 -1违约 | |

## 房间配置

可预约: A101日新阁, A103致知堂, A105聚思轩, B102韵音阁
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
