# 笃学书院空间预约系统 v2 架构

## 当前架构结论

`miniprogram/` 是正式的 v2 微信前端主线，不是废弃目录。v2 延续第一版原生小程序的紫色主题、自定义底部导航、空间导览和双页预约交互，把原先的微信云函数调用替换为 FastAPI REST API。

仓库中其他前端/后端目录的定位如下：

| 目录 | 当前定位 | 是否属于正式 v2 运行链路 |
|---|---|---|
| `miniprogram/` | 原生微信小程序，正式交付前端 | 是 |
| `backend/` | FastAPI、业务事务、数据库、照片与消息 outbox | 是 |
| `frontend/` | 此前的 uni-app/H5 实验实现，供页面和业务逻辑参考 | 否 |
| `cloudfunctions/` | 第一版微信云函数参考代码 | 否 |
| `deploy/` | 学校服务器 nginx 与容器部署参考 | 生产部署时使用 |

后续开发不得再把 `miniprogram/` 标为“v1 废弃版”，也不得要求微信开发者工具导入 `frontend/dist/`。微信开发者工具应直接导入仓库根目录，由根目录 `project.config.json` 的 `miniprogramRoot: "miniprogram/"` 加载正式前端。

## 运行链路

```text
原生微信小程序 miniprogram/
  ├── 紫色页面、空间导览、自定义 TabBar
  ├── app.js：登录态和统一 request/upload 入口
  └── utils/api.js：API 地址、JWT、错误解析
                    │
                    │ HTTPS + JSON / multipart + Bearer JWT
                    ▼
FastAPI backend/app/
  ├── routers：HTTP 接口、鉴权依赖和响应模型
  ├── services.py：分房、冲突、审批、清扫、限制和事务边界
  ├── SQLAlchemy async
  └── notifications outbox + 分钟任务
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
PostgreSQL（生产）      微信订阅消息 API
SQLite（本地演示）      照片持久化目录/对象存储
```

正式 v2 不依赖微信云数据库、云存储或云函数。`cloudfunctions/` 可用于理解第一版行为，但主数据只应写入 FastAPI 所连接的数据库。

## 原生小程序页面

| 页面 | 职责与当前边界 |
|---|---|
| `pages/login/login` | 学号密码登录，保存 JWT；已有有效 token 时恢复登录 |
| `pages/login/register` | 学号、姓名、手机号、4 位班级和密码注册 |
| `pages/login/forgot` | 当前仅提示联系书院管理员；短信验证码找回尚未接入 |
| `pages/index/index` | 紫色空间导览、楼层图、公开状态、场景预约入口 |
| `pages/room/room` | 房间资料、今日占用时间轴、公开空间状态和使用者留言；预约按钮进入对应场景，不指定最终房间 |
| `pages/reserve/reserve` | 选择四类场景、人数、日期和连续时段；读取运行配置和场景可用性 |
| `pages/reserve/form` | 填写用途、上传玉兰卡、订阅消息授权、提交自动分房申请 |
| `pages/my/my` | 状态列表、取消、签到/扫码签到、清扫照片、再次预约、通知设置和限制状态 |
| `pages/admin/admin` | 单页多标签后台：概览、预约审核、清扫复核、用户限制、分房规则、系统参数、Excel 与签到码内容 |

前端先上传玉兰卡照片取得一次性的私密 `media_id`，创建预约时只提交场景、日期、slot 区间、人数、用途和该媒体编号，绝不提交最终房间。后端在同一事务中校验媒体所有者、用途、有效期与复用状态，并重新校验资格、时长、冲突和容量。

## API 分层

| 路由组 | 主要用途 |
|---|---|
| `/api/auth` | 注册、登录、当前用户、绑定微信 OpenID |
| `/api/rooms` | 空间列表、详情、单个房间占用时段、实际使用者留言与留言照片 |
| `/api/reservations` | 运行配置、场景可用性、创建、我的预约、取消、签到、玉兰卡/清扫照片 |
| `/api/media/{media_id}` | 仅管理员鉴权下载玉兰卡/清扫照片，并写入访问审计 |
| `/api/admin` | 统计、审批、清扫复核、用户/违约/限制、系统参数、分房规则、辅导员导入、Excel |
| `/api/notifications` | 返回已配置的订阅消息模板 ID |

`miniprogram/utils/api.js` 负责为请求和上传统一附加 JWT，并把 FastAPI 的错误结构转成可展示文本。401 仅在响应对应的 token 仍是当前 token 时清除登录态，避免冷启动并发请求误删新会话。业务安全不能依赖前端按钮是否显示，后端必须始终执行最终校验。

## 核心数据表

| 表 | 关键字段与用途 |
|---|---|
| `users` | 学号、角色、密码摘要、微信 OpenID、启用状态 |
| `rooms` | 房间基础资料、物理容量、公开状态 |
| `room_scene_rules` | 场景、候选房间、优先级、场景容量、共享/独占和启用状态 |
| `reservations` | 场景、自动分配房间、日期、slot、人数、用途、玉兰卡、审核与使用状态 |
| `cleanup_verifications` | 清扫照片、提交/复核状态、备注和复核人 |
| `private_media` | 敏感媒体所有者、用途、预约归属、存储键、有效状态和到期时间 |
| `media_access_logs` | 管理员读取敏感媒体的访问审计 |
| `booking_restrictions` | 临时/限时/永久限制、原因、创建人、到期与撤销状态 |
| `system_settings` | 开放时间、预约上限、审批时间等运行参数 |
| `notifications` | 消息类型、载荷、计划时间、发送状态、重试次数与错误 |
| `violations` | 未签到和清扫不合格记录，用于自动限制预约 |
| `space_messages` | 房间使用者留言、照片 URL、展示作者和创建时间 |

v2 不恢复第一版的“信用分”。用户侧展示预约限制状态，管理员侧查看有效违约和限制记录；每累计达到配置阈值时由后端生成限时限制。

## 分房和时长规则

- 自习：A102 → A101 → A105，共享，一人一约。
- 开会：学生 A105 → A101 → A102；辅导员优先 A106，独占。
- 大型活动：仅 A103，独占。
- 音乐练习：B102 优先，A103 钢琴为备选；A103 钢琴仅在配置时段内可用。
- A103 上的大型活动与音乐练习按同一物理房间互斥，B102 保持独立。
- 待审核申请也占用候选房间容量，防止审批前超卖。
- 默认 30 分钟一个 slot；`end_slot` 为开区间。
- 每日时长按所有有效占用状态累计，取消和驳回不计入。

管理员可修改运行参数和分房规则，因此原生预约页先读取 `/reservations/config`，再按登录角色、场景、日期和人数读取 `/reservations/availability`。接口返回每个 slot 的候选房间，页面对连续区间取交集，保证整段至少有同一间房；提交时后端仍会再次检查，避免并发变化造成错误预约。

## 状态流

```text
pending ──人工审核/自动审批──> approved ──签到──> in_use ──结束──> cleanup_pending
   │                              │                                  │
   ├── rejected                   ├── missed                         ├── completed
   └── cancelled                  └── cancelled                      └── cleanup_rejected
                                                                          │
                                                                          └──重传照片──> cleanup_pending
```

`cleanup_pending` 可能表示“等待上传”或“照片已上传、等待复核”，是否存在 `cleanup` 记录用于区分。尚未上传或清扫被退回时会阻断下一次预约；照片成功提交后先解除该阻断，再由管理员异步复核。

## 定时任务与部署边界

独立 worker 的分钟任务用于推进超时状态、在配置时刻自动审批和投递消息：

- API 生命周期不启动调度器；生产必须单独运行 `python -m app.worker`。
- PostgreSQL advisory lock 保证多个 worker 只有一个执行当前 tick，任务结果和最后成功心跳写入 `system_settings`。
- 生产 API 只检查 Alembic revision，不隐式创建或修改 schema；发布顺序必须为迁移、API/worker、readiness、流量切换。
- SQLite 只用于本地演示，生产应使用 PostgreSQL；SQLite 不具备与 PostgreSQL 等价的并发锁语义。
- 留言图片写入 `UPLOAD_DIR`；敏感图片写入独立的 `PRIVATE_UPLOAD_DIR`，默认 90 天后由任务删除。生产必须使用隔离的持久化磁盘或校内对象存储。

## 当前未完成或依赖外部条件

1. 短信验证码找回密码尚未接入，`pages/login/forgot` 只提供联系管理员说明。
2. 真实微信账号绑定和订阅消息需要正式 AppID、AppSecret、模板 ID 和微信合法域名；配置为空时预约仍可提交，但不会真实发送消息。
3. 签到码当前由管理员复制 JSON 内容，二维码图片仍需外部工具或后续页面生成。
4. `frontend/` 不是当前 H5 正式交付物；如学校确需 H5，应单独立项确认并与原生端业务同步。
5. 预约、待审核、清扫和用户列表默认每页 30 条、最多 100 条，响应包含 `total/limit/offset/has_more`；Excel 导出使用独立完整查询，不受页面大小影响。

## 学校服务器交接范围

交付学校时至少应明确以下责任：

- 学校提供服务器、正式域名、HTTPS 证书、DNS/备案条件和防火墙策略。
- 学校运维保管 `backend/.env`、数据库账号、AppSecret 和模板 ID，不写入 Git。
- 生产数据库使用 PostgreSQL，并建立备份、恢复和容量策略。
- `UPLOAD_DIR` 仅保存公开留言图片；`PRIVATE_UPLOAD_DIR` 单独持久化且不得由 nginx 静态暴露，保存期限由 `MEDIA_RETENTION_DAYS` 控制。
- nginx 代理 `/api/` 与 `/uploads/`，API 与独立 worker 具备开机启动、JSON 日志、request/job ID 和 readiness 监控。
- 上线前替换默认 `SECRET_KEY`、默认管理员凭据，并完成学生/管理员真机全流程验收。
