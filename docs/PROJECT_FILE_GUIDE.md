# 项目目录与文件用途说明

依据当前仓库逐文件整理。目录以仓库根目录为起点，最多展开三层文件夹；例如 `backend/app/domain/` 和 `miniprogram/pages/login/` 均为三层。同类文件逐项列出，但不展开第三方依赖与生成缓存。

正式运行链路：手机微信中的 `miniprogram/` → HTTPS请求 → 学校服务器中的 `backend/` → PostgreSQL及照片存储。小程序前端上传微信平台，后端部署到学校服务器；源码、密钥和运行数据各自管理。

## 阅读前先认识文件类型

| 后缀 | 含义 |
|---|---|
| `.js` / `.mjs` / `.cjs` | JavaScript逻辑或Node脚本；mjs/cjs区分模块格式 |
| `.wxml` | 微信小程序页面/组件结构，类似网页HTML |
| `.wxss` | 微信小程序样式，类似CSS |
| `.json` | 配置或结构化数据，不是数据库 |
| `.py` | Python后端逻辑、脚本或测试 |
| `.md` | Markdown文档，可在GitHub直接阅读 |
| `.yml` | 配置，如容器、GitHub工作流或表单 |
| `.vue` | 历史Vue/uni-app单文件组件 |
| `.sh` / `.cmd` | Linux/macOS shell脚本 / Windows命令脚本 |
| `.png` | 图片素材 |

一个页面通常有四个同名文件：JS处理逻辑、WXML定义结构、WXSS定义样式、JSON配置页面。例如修改登录按钮文字看 `login.wxml`，修改登录请求看 `login.js`。

## 顶层目录

| 目录 | 用途 | 交付地位 |
|---|---|---|
| `miniprogram/` | 正式原生微信小程序前端 | 用户手机界面，上传微信 |
| `backend/` | 正式FastAPI后端、迁移及测试 | 部署学校服务器 |
| `scripts/` | 构建和测试、发布检查 | 开发与交付工具 |
| `deploy/` | nginx和备份恢复脚本 | 学校运维材料 |
| `docs/` | 架构、教程、验收和报告 | 交付文档 |
| `.github/` | GitHub检查、评审和反馈配置 | 协作工具 |
| `frontend/` | 历史uni-app/H5实现 | 参考，非正式微信端 |
| `cloudfunctions/` | 第一版微信云开发后端 | 参考，非正式后端 |

## 根目录文件

| 文件 | 用途 |
|---|---|
| `.dockerignore` | 排除根ops镜像构建上下文中的密钥、业务文件、备份与缓存。 |
| `.env.example` | Compose插值模板，根.env与直接Python backend/.env分开。 |
| `.gitignore` | 规定哪些本地文件不提交到 Git，例如密钥、数据库、照片、依赖和构建结果。 |
| `AGENTS.md` | AI 修改仓库时应遵守的主线、架构、隐私和测试约定。 |
| `CHANGELOG.md` | 版本变更记录，便于维护者了解新增、修复及兼容性变化。 |
| `CLAUDE.md` | AI协作约定，已同步正式原生主线/domain/构建与交付边界；AGENTS.md及实际守护优先。 |
| `CODE_OF_CONDUCT.md` | 协作行为规范。 |
| `CONTRIBUTING.md` | 开发贡献流程：分支、测试、PR、评审和修改边界。 |
| `README.md` | 项目总入口：用途、架构、启动、测试和文档链接。 |
| `ROADMAP.md` | 后续计划、待完成工作和外部阻断项。 |
| `SECURITY.md` | 安全问题的私下报告方式与处理原则。 |
| `SUPPORT.md` | 支持范围、问题反馈和维护边界。 |
| `Sheet_20250907.example.csv` | 辅导员导入 CSV 样例，用于说明列格式，不是学校真实人员名单。 |
| `docker-compose.yml` | 服务器容器部署模板，组合 PostgreSQL、数据库迁移、API、worker 与持久化卷。 |
| `eng-vibe.config.json` | 配置仓库约定检查命令，指向 backend/guard.cmd。 |
| `package.json` | 仓库级 Node 命令入口，定义测试、开发/体验/正式构建和发布检查。 |
| `project.config.json` | 微信开发者工具项目配置；指定 miniprogram/ 为前端根目录，记录 AppID 和编译设置。 |

## 正式小程序：入口与配置

| 文件 | 用途 |
|---|---|
| `miniprogram/app.js` | 整个小程序的运行入口，管理登录态、请求/上传/下载、登录恢复和全局状态。 |
| `miniprogram/app.json` | 全局页面注册、导航栏和底部 tabBar 配置。新增页面必须在这里登记。 |
| `miniprogram/app.wxss` | 全局样式与公共色彩、布局规则。 |
| `miniprogram/build.config.js` | 源码中的本地开发默认配置；构建脚本会在产物里生成目标环境配置。 |
| `miniprogram/config.js` | 读取构建配置并统一处理 API 地址和服务器图片地址；开发环境允许调试覆盖。 |
| `miniprogram/sitemap.json` | 微信搜索索引规则，控制哪些页面允许被索引。 |
| `miniprogram/static/logo.png` | 小程序 Logo 图片素材。 |

## 正式小程序：底部导航

| 文件 | 用途 |
|---|---|
| `miniprogram/custom-tab-bar/index.js` | 底部导航逻辑：切换空间导览/我的及选中状态。 |
| `miniprogram/custom-tab-bar/index.json` | 声明这是一个自定义组件。 |
| `miniprogram/custom-tab-bar/index.wxml` | 底部导航按钮结构。 |
| `miniprogram/custom-tab-bar/index.wxss` | 底部导航样式。 |

## 正式小程序：公共工具

| 文件 | 用途 |
|---|---|
| `miniprogram/utils/admin-config.js` | 管理配置表单逻辑：禁约、清扫复核、系统参数、房间规则及参数校验。 |
| `miniprogram/utils/admin-presenters.js` | 把后台数据转成页面展示内容，例如时间、场景、角色、照片编号及禁约状态。 |
| `miniprogram/utils/admin-state.js` | 管理页标签、分页、搜索和选中记录等状态辅助逻辑。 |
| `miniprogram/utils/admin-tools.js` | Excel 导出筛选、状态/场景选项、签到二维码扫描数据等管理工具逻辑。 |
| `miniprogram/utils/admin-workflows.js` | 管理页扩展：全部订单、违规与清扫待办、审计分页、私密照片预览、密码恢复与禁约起止输入。 |
| `miniprogram/utils/api.js` | 底层网络封装，统一 wx.request、上传/下载、Bearer token、错误和401处理。 |
| `miniprogram/utils/booking-flow.js` | 预约、清扫、审核请求参数与连续时段选择、登录状态等纯逻辑。 |
| `miniprogram/utils/reservations.js` | 预约列表分页数据兼容、状态文字、筛选和可执行操作判断。 |

## 正式小程序：pages/login/

| 文件 | 用途 |
|---|---|
| `miniprogram/pages/login/forgot.js` | 忘记密码说明，以及进入管理员凭证恢复页面的入口。 页面逻辑：数据加载、事件处理和接口调用。 |
| `miniprogram/pages/login/forgot.json` | 忘记密码说明，以及进入管理员凭证恢复页面的入口。 页面配置：标题、组件或刷新等设置。 |
| `miniprogram/pages/login/forgot.wxml` | 忘记密码说明，以及进入管理员凭证恢复页面的入口。 页面结构：输入框、按钮、列表和条件显示。 |
| `miniprogram/pages/login/forgot.wxss` | 忘记密码说明，以及进入管理员凭证恢复页面的入口。 页面样式：布局、颜色、字体和间距。 |
| `miniprogram/pages/login/login.js` | 学号密码登录，以及已绑定账号的微信登录；处理首次换密跳转。 页面逻辑：数据加载、事件处理和接口调用。 |
| `miniprogram/pages/login/login.json` | 学号密码登录，以及已绑定账号的微信登录；处理首次换密跳转。 页面配置：标题、组件或刷新等设置。 |
| `miniprogram/pages/login/login.wxml` | 学号密码登录，以及已绑定账号的微信登录；处理首次换密跳转。 页面结构：输入框、按钮、列表和条件显示。 |
| `miniprogram/pages/login/login.wxss` | 学号密码登录，以及已绑定账号的微信登录；处理首次换密跳转。 页面样式：布局、颜色、字体和间距。 |
| `miniprogram/pages/login/password.js` | 修改当前密码，或使用管理员一次性凭证重置密码。 页面逻辑：数据加载、事件处理和接口调用。 |
| `miniprogram/pages/login/password.json` | 修改当前密码，或使用管理员一次性凭证重置密码。 页面配置：标题、组件或刷新等设置。 |
| `miniprogram/pages/login/password.wxml` | 修改当前密码，或使用管理员一次性凭证重置密码。 页面结构：输入框、按钮、列表和条件显示。 |
| `miniprogram/pages/login/password.wxss` | 修改当前密码，或使用管理员一次性凭证重置密码。 页面样式：布局、颜色、字体和间距。 |
| `miniprogram/pages/login/register.js` | 注册表单：学号、姓名、手机、班级和密码。注册启用不等于学校身份已核验。 页面逻辑：数据加载、事件处理和接口调用。 |
| `miniprogram/pages/login/register.json` | 注册表单：学号、姓名、手机、班级和密码。注册启用不等于学校身份已核验。 页面配置：标题、组件或刷新等设置。 |
| `miniprogram/pages/login/register.wxml` | 注册表单：学号、姓名、手机、班级和密码。注册启用不等于学校身份已核验。 页面结构：输入框、按钮、列表和条件显示。 |
| `miniprogram/pages/login/register.wxss` | 注册表单：学号、姓名、手机、班级和密码。注册启用不等于学校身份已核验。 页面样式：布局、颜色、字体和间距。 |

## 正式小程序：pages/index/

| 文件 | 用途 |
|---|---|
| `miniprogram/pages/index/index.js` | 空间导览首页，加载房间并进入详情或预约。 页面逻辑：数据加载、事件处理和接口调用。 |
| `miniprogram/pages/index/index.json` | 空间导览首页，加载房间并进入详情或预约。 页面配置：标题、组件或刷新等设置。 |
| `miniprogram/pages/index/index.wxml` | 空间导览首页，加载房间并进入详情或预约。 页面结构：输入框、按钮、列表和条件显示。 |
| `miniprogram/pages/index/index.wxss` | 空间导览首页，加载房间并进入详情或预约。 页面样式：布局、颜色、字体和间距。 |

## 正式小程序：pages/room/

| 文件 | 用途 |
|---|---|
| `miniprogram/pages/room/room.js` | 房间详情、使用时段、公开状态和实际使用者留言。 页面逻辑：数据加载、事件处理和接口调用。 |
| `miniprogram/pages/room/room.json` | 房间详情、使用时段、公开状态和实际使用者留言。 页面配置：标题、组件或刷新等设置。 |
| `miniprogram/pages/room/room.wxml` | 房间详情、使用时段、公开状态和实际使用者留言。 页面结构：输入框、按钮、列表和条件显示。 |
| `miniprogram/pages/room/room.wxss` | 房间详情、使用时段、公开状态和实际使用者留言。 页面样式：布局、颜色、字体和间距。 |

## 正式小程序：pages/reserve/

| 文件 | 用途 |
|---|---|
| `miniprogram/pages/reserve/form.js` | 填写人数、申请理由、上传玉兰卡、提交预约及申请通知授权。 页面逻辑：数据加载、事件处理和接口调用。 |
| `miniprogram/pages/reserve/form.json` | 填写人数、申请理由、上传玉兰卡、提交预约及申请通知授权。 页面配置：标题、组件或刷新等设置。 |
| `miniprogram/pages/reserve/form.wxml` | 填写人数、申请理由、上传玉兰卡、提交预约及申请通知授权。 页面结构：输入框、按钮、列表和条件显示。 |
| `miniprogram/pages/reserve/form.wxss` | 填写人数、申请理由、上传玉兰卡、提交预约及申请通知授权。 页面样式：布局、颜色、字体和间距。 |
| `miniprogram/pages/reserve/reserve.js` | 选择场景、日期和连续时段，查询可用性。 页面逻辑：数据加载、事件处理和接口调用。 |
| `miniprogram/pages/reserve/reserve.json` | 选择场景、日期和连续时段，查询可用性。 页面配置：标题、组件或刷新等设置。 |
| `miniprogram/pages/reserve/reserve.wxml` | 选择场景、日期和连续时段，查询可用性。 页面结构：输入框、按钮、列表和条件显示。 |
| `miniprogram/pages/reserve/reserve.wxss` | 选择场景、日期和连续时段，查询可用性。 页面样式：布局、颜色、字体和间距。 |

## 正式小程序：pages/my/

| 文件 | 用途 |
|---|---|
| `miniprogram/pages/my/my.js` | 个人信息、预约列表、取消/签到/清扫、通知授权和管理入口。 页面逻辑：数据加载、事件处理和接口调用。 |
| `miniprogram/pages/my/my.json` | 个人信息、预约列表、取消/签到/清扫、通知授权和管理入口。 页面配置：标题、组件或刷新等设置。 |
| `miniprogram/pages/my/my.wxml` | 个人信息、预约列表、取消/签到/清扫、通知授权和管理入口。 页面结构：输入框、按钮、列表和条件显示。 |
| `miniprogram/pages/my/my.wxss` | 个人信息、预约列表、取消/签到/清扫、通知授权和管理入口。 页面样式：布局、颜色、字体和间距。 |
| `miniprogram/pages/my/notifications.js` | 当前用户的预约和资格消息列表、发送状态与分页。 页面逻辑：数据加载、事件处理和接口调用。 |
| `miniprogram/pages/my/notifications.json` | 当前用户的预约和资格消息列表、发送状态与分页。 页面配置：标题、组件或刷新等设置。 |
| `miniprogram/pages/my/notifications.wxml` | 当前用户的预约和资格消息列表、发送状态与分页。 页面结构：输入框、按钮、列表和条件显示。 |
| `miniprogram/pages/my/notifications.wxss` | 当前用户的预约和资格消息列表、发送状态与分页。 页面样式：布局、颜色、字体和间距。 |

## 正式小程序：pages/admin/

| 文件 | 用途 |
|---|---|
| `miniprogram/pages/admin/admin.js` | 管理主页面：审核、清扫、用户、禁约、订单、待办、日志、规则、配置及导出。 页面逻辑：数据加载、事件处理和接口调用。 |
| `miniprogram/pages/admin/admin.json` | 管理主页面：审核、清扫、用户、禁约、订单、待办、日志、规则、配置及导出。 页面配置：标题、组件或刷新等设置。 |
| `miniprogram/pages/admin/admin.wxml` | 管理主页面：审核、清扫、用户、禁约、订单、待办、日志、规则、配置及导出。 页面结构：输入框、按钮、列表和条件显示。 |
| `miniprogram/pages/admin/admin.wxss` | 管理主页面：审核、清扫、用户、禁约、订单、待办、日志、规则、配置及导出。 页面样式：布局、颜色、字体和间距。 |

## 后端：入口脚本和配置

| 文件 | 用途 |
|---|---|
| `backend/.env.example` | 后端环境变量模板；有配置键和示例值，不包含实际 AppSecret 等生产密钥。 |
| `backend/.dockerignore` | 排除密钥、数据库、照片、凭据和缓存进入Docker构建上下文。 |
| `backend/init_reference_data.py` | 生产迁移后显式补缺失房间和规则，保留学校已有配置，不创建账号。 |
| `backend/Dockerfile` | 构建 Python 后端容器镜像，安装依赖并定义服务运行方式。 |
| `backend/alembic.ini` | Alembic 数据库迁移工具配置。 |
| `backend/create_admin.py` | 服务器终端交互创建正式管理员；确认密码并拒绝覆盖或提升已有账号。 |
| `backend/demo_seed.py` | 生成虚构账号和预约记录，供本地演示与验收练习。 |
| `backend/guard.cmd` | Windows 运行仓库约定检查的命令脚本。 |
| `backend/import_counselors.py` | 受控 CSV 导入辅导员；随机初始密码写入权限0600文件，新账号首次必须改密。 |
| `backend/pytest.ini` | 后端测试发现规则及 pytest 配置。 |
| `backend/requirements.txt` | 后端 Python 第三方依赖及版本。 |
| `backend/seed.py` | 本地初始化房间、规则、配置及演示管理员；生产拒绝执行。 |
| `backend/test_postgres_concurrency.py` | PostgreSQL 实际并发验证，检查数据库行锁与预约竞争；需专门测试环境。 |

## 后端：app/公共基础

| 文件 | 用途 |
|---|---|
| `backend/app/__init__.py` | Python 包标识，使这个目录作为可导入模块使用；业务不集中在该文件。 |
| `backend/app/auth.py` | 密码哈希、JWT 签发/验证、会话版本和当前用户/管理员/辅导员权限检查。 |
| `backend/app/config.py` | 读取环境变量，管理数据库、密钥、微信、上传等配置并进行运行安全检查。 |
| `backend/app/database.py` | 建立数据库引擎和会话，检查迁移版本并处理 SQLite 本地兼容初始化。 |
| `backend/app/reference_data.py` | 房间和场景规则的共享默认定义，不包含演示账号。 |
| `backend/app/main.py` | FastAPI 程序入口，挂载路由、中间件、静态文件与健康/就绪检查。 |
| `backend/app/media_view.html` | Excel 照片链接打开的管理员鉴权页，登录后读取私密图片，不公开图片内容。 |
| `backend/app/models.py` | 数据库表、字段、关系、业务枚举及上海时区的 local_now；结构变化需对应迁移。 |
| `backend/app/notifications.py` | 微信接口凭证、订阅模板映射、消息队列投递和发送结果处理。 |
| `backend/app/observability.py` | 结构化日志和请求/任务追踪等可观测性辅助。 |
| `backend/app/queries.py` | 常用列表查询：分页、筛选及关联数据加载。 |
| `backend/app/schemas.py` | 接口输入/输出模型与校验，决定允许提交什么和向前端返回什么。 |
| `backend/app/services.py` | 旧业务调用兼容入口，转发到 domain；新业务主要写在各 domain 模块。 |
| `backend/app/tasks.py` | 一次 worker 任务：状态收尾、禁约到期、媒体清理、自动审批、消息发送与任务心跳。 |
| `backend/app/uploads.py` | 图片上传格式、大小和签名检查，区分公开留言图与私密核验图存储。 |
| `backend/app/worker.py` | 独立后台任务进程的启动与循环入口，部署时与 API 分开运行。 |

## 后端：app/domain/业务处理

| 文件 | 用途 |
|---|---|
| `backend/app/domain/__init__.py` | Python 包标识，使这个目录作为可导入模块使用；业务不集中在该文件。 |
| `backend/app/domain/reference_data.py` | 只新增缺失基础数据，PostgreSQL并发初始化串行化并记录审计。 |
| `backend/app/domain/accounts.py` | 修改密码、30分钟一次性恢复凭证、旧会话撤销与微信绑定清除。 |
| `backend/app/domain/audit.py` | 管理操作审计记录的统一写入函数。 |
| `backend/app/domain/common.py` | 共享时间函数、消息入队，以及占用状态/每日额度状态定义。 |
| `backend/app/domain/media.py` | 私密照片归属、用途、预约绑定、授权读取与到期清理。 |
| `backend/app/domain/reservations.py` | 核心预约业务：可用性、自动分房、时间/容量/额度、取消、签到及状态流转。 |
| `backend/app/domain/restrictions.py` | 禁约新增/解除/到期、起止时间判断、违约记录与累计处罚。 |
| `backend/app/domain/reviews.py` | 管理员预约审核、清扫复核和自动审批业务。 |
| `backend/app/domain/rooms.py` | 房间及公开空间状态、留言权限与留言业务。 |
| `backend/app/domain/settings.py` | 读取/更新系统运行参数，并校验配置组合、记录变更。 |
| `backend/app/domain/users.py` | 用户查询、创建和辅导员账户处理，拒绝静默提升已有学生账号。 |

## 后端：app/routers/接口入口

| 文件 | 用途 |
|---|---|
| `backend/app/routers/__init__.py` | Python 包标识，使这个目录作为可导入模块使用；业务不集中在该文件。 |
| `backend/app/routers/admin.py` | 管理接口：统计、审核、用户、禁约、规则、系统配置、二维码、Excel、辅导员导入。 |
| `backend/app/routers/auth.py` | 对外账号接口：注册、登录、个人资料、微信绑定/登录、改密和凭证恢复。 |
| `backend/app/routers/management.py` | 本轮新增的管理接口：密码恢复签发、操作日志与违规/清扫待办分页。 |
| `backend/app/routers/media.py` | 管理员鉴权照片下载及浏览器照片查看页入口。 |
| `backend/app/routers/notifications.py` | 公开订阅模板编号及当前用户自己的消息记录接口。 |
| `backend/app/routers/reservations.py` | 场景配置、可用性、申请、我的预约、取消、签到与清扫上传接口。 |
| `backend/app/routers/rooms.py` | 房间列表、详情、时段、留言和留言照片接口。 |

## 后端：migrations/数据库升级

| 文件 | 用途 |
|---|---|
| `backend/migrations/env.py` | 连接目标数据库和表模型，执行 Alembic 迁移。 |
| `backend/migrations/script.py.mako` | 生成新迁移文件时使用的代码模板。 |
| `backend/migrations/versions/20260813_01_schema_baseline.py` | 初始数据库结构的迁移基线。 |
| `backend/migrations/versions/20260813_02_reservation_query_indexes.py` | 为预约列表查询增加索引，提高查询效率。 |
| `backend/migrations/versions/20261002_03_account_recovery_audit.py` | 增加会话版本、首次换密、恢复凭证和操作日志结构。 |

## 后端：guards/与tests/自动检查

| 文件 | 用途 |
|---|---|
| `backend/guards/test_conventions.py` | 检查代码是否遵守架构、时间、状态、视觉等约定。 |
| `backend/tests/conftest.py` | 测试公共准备：隔离临时数据库/照片目录、客户端和测试初始化。 |
| `backend/tests/test_reference_data.py` | 隔离空库测试生产初始化、重复执行、补缺项以及保留账号和配置。 |
| `backend/tests/test_business.py` | 核心业务流程、自动分房、权限、日限额、审核、清扫、违约及导出回归。 |
| `backend/tests/test_delivery_progress.py` | 本轮额度、长期停机、审批补偿、禁约边界、恢复凭证、会话撤销和首次换密回归。 |
| `backend/tests/test_demo_seed.py` | 虚构演示数据初始化和安全边界测试。 |
| `backend/tests/test_operations.py` | 健康就绪、迁移版本、任务唯一执行、心跳及通知异常处理测试。 |
| `backend/tests/test_pagination.py` | 列表分页、续载及响应契约测试。 |
| `backend/tests/test_query_indexes.py` | 数据库查询索引存在性及相关结构检查。 |
| `backend/tests/test_security.py` | 生产配置、私密照片归属、角色鉴权、审计及到期删除测试。 |
| `backend/tests/test_state_matrix.py` | 预约状态与允许操作、时限边界的矩阵测试。 |

## scripts/构建、测试和发布检查

| 文件 | 用途 |
|---|---|
| `scripts/check-handover-docs.py` | 只读校验当前交付文档的本地文件链接与Markdown锚点。 |
| `scripts/verify-deployment-recovery.py` | 使用两个临时Compose项目验证实际部署、加密备份、空目标恢复、数据库/照片一致与重启持久化。 |
| `scripts/verify-container-handover.py` | 创建并清理临时PostgreSQL、网络和凭据卷，运行镜像交付检查。 |
| `scripts/container-handover-smoke.py` | 容器内执行虚构数据的迁移、初始化、建号、导入和预约验证。 |
| `scripts/build-miniprogram.mjs` | 生成三种小程序产物，开发回退根AppID；正式要求显式配置、版本和完整提交，记录完整文件清单与SHA-256。 |
| `scripts/build-miniprogram.test.mjs` | 验证配置门禁、源码不变、完整清单、摘要稳定/变化及产物改动检测。 |
| `scripts/verify-miniprogram-build.mjs` | 校验构建目录与清单是否一致，检测文件缺失、新增和修改。 |
| `scripts/miniprogram-api.test.cjs` | 请求、令牌、401并发与错误信息处理测试。 |
| `scripts/miniprogram-domain.test.cjs` | 预约展示、分页、状态、导出和二维码相关纯逻辑测试。 |
| `scripts/miniprogram-flow.test.cjs` | 申请/清扫/审核参数、连续时段、管理表单及禁约区间测试。 |
| `scripts/release-check.mjs` | 发布前检查版本、文档、工作区等候选版要求；不能替代真机和生产验收。 |
| `scripts/release-check.test.mjs` | 发布检查与交付基础文档的回归测试。 |

## deploy/服务器材料

| 文件 | 用途 |
|---|---|
| `deploy/backup.sh` | 停写确认后调用备份工具生成数据库+公开/私密照片加密快照；保留策略由学校决定。 |
| `deploy/backup_restore.py` | 成套密文摘要/归档验证、空目标与迁移URL核对，实际备份/恢复逻辑。 |
| `deploy/Dockerfile.ops` | 打包PostgreSQL16客户端、age与Python备份工具。 |
| `deploy/duxue-api.service.example` | 无Docker时的API systemd模板，需学校修改路径/账号并实际验证。 |
| `deploy/duxue-worker.service.example` | 无Docker时的独立worker systemd模板。 |
| `deploy/nginx.conf` | HTTPS 入口前的 nginx 反向代理模板，路由 API 与公开图片并限制上传。 |
| `deploy/restore.sh` | 恢复数据库与双媒体到空目标，核对迁移URL；迁移是显式下一步，不隐式执行。 |

## docs/说明与验收材料

| 文件 | 用途 |
|---|---|
| `docs/PROJECT_FILE_GUIDE.md` | 本说明，逐项解释项目目录、文件类型与修改入口。 |
| `docs/AI_PROGRESS_AUDIT_GUIDE.md` | 交给 AI 的项目结构、GitHub 状态和进度检查步骤。 |
| `docs/ARCHITECTURE.md` | 正式前后端架构和模块边界说明。 |
| `docs/BUILD_ARTIFACT_GUIDE.md` | AppID策略、跨平台构建命令、版本/提交要求和产物摘要校验说明。 |
| `docs/BUILD_ARTIFACT_REPORT.md` | 03–04构建修改的本地验证结果与范围。 |
| `docs/USER_GUIDE.md` | 学生、辅导员与管理员操作、恢复/换密、订单/待办、限制和导出教程。 |
| `docs/DEPLOYMENT_GUIDE.md` | 固定版本、空服务器、Compose/直接Python、HTTPS、持久化、升级回滚教程。 |
| `docs/HANDOVER_DOCUMENTATION_REPORT.md` | 05–11教程与实际隔离部署/恢复的证据和学校验收边界。 |
| `docs/DEMO.md` | 使用虚构数据进行演示和验收练习的流程。 |
| `docs/DEPENDENCY_LICENSE_INVENTORY.md` | 依赖许可证记录及交付核查材料。 |
| `docs/GITHUB_ADMIN_SETUP.md` | GitHub 权限、分支保护和自动检查等管理员设置说明。 |
| `docs/LOCAL_COMPLETION_REPORT.md` | 较早一轮本地工作完成记录，应注意记录日期和版本。 |
| `docs/LOCAL_FUNCTION_PROGRESS_20261002.md` | 2026-10-02新增功能与本地测试报告。 |
| `docs/OPERATIONS_RUNBOOK.md` | 服务器运行、健康检查、备份恢复、升级回滚和账号恢复说明。 |
| `docs/PILOT_METRICS.md` | 校内试点汇总指标模板。 |
| `docs/PILOT_RELEASE_BASELINE.md` | 试点候选版的范围和发布准入条件。 |
| `docs/RELEASE_CHECKLIST.md` | 候选发布和正式交接的验证、配置、签字清单。 |
| `docs/REQUIREMENTS_TRACEABILITY.md` | 需求与实现、验证证据的对照表。 |
| `docs/WECHAT_SETUP.md` | 微信平台、AppID/AppSecret、域名、通知与真机配置说明。 |
| `docs/assets/screenshots/README.md` | 真实脱敏产品截图的存放与取证说明；不代表已经完成截图验收。 |

## .github/GitHub协作配置

| 文件 | 用途 |
|---|---|
| `.github/CODEOWNERS` | 声明哪些维护者应审核哪些文件。 |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | 缺陷反馈表单。 |
| `.github/ISSUE_TEMPLATE/config.yml` | 配置 Issue 模板入口和反馈渠道。 |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | 新增功能需求表单。 |
| `.github/ISSUE_TEMPLATE/pilot_acceptance.yml` | 校内试点验收事项记录表单。 |
| `.github/pull_request_template.md` | 提交 PR 时填写问题、改动、验证及风险的模板。 |
| `.github/workflows/quality.yml` | GitHub 自动质量检查：后端/并发/前端测试、迁移、构建及依赖审计。当前由 PR、main 推送或版本标签触发，partner 普通推送不会自动触发。 |

## frontend/历史参考前端

| 文件 | 用途 |
|---|---|
| `frontend/.env.example` | 历史前端环境配置模板。 |
| `frontend/App.vue` | 历史 uni-app 应用根组件。 |
| `frontend/api/index.js` | 历史前端后端接口调用封装。 |
| `frontend/index.html` | 历史 H5 网页入口。 |
| `frontend/main.js` | 历史 uni-app/Vue 应用启动入口。 |
| `frontend/manifest.json` | 历史 uni-app 应用标识和各平台打包配置。 |
| `frontend/package-lock.json` | 锁定历史前端依赖版本，方便复现安装。 |
| `frontend/package.json` | 历史前端依赖和编译命令。 |
| `frontend/pages.json` | 历史 uni-app 页面的路由与窗口配置。 |
| `frontend/pages/admin/cleanup.vue` | 历史清扫复核，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/pages/admin/counselors.vue` | 历史辅导员管理，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/pages/admin/dashboard.vue` | 历史管理概览，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/pages/admin/reservations.vue` | 历史预约审核，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/pages/admin/settings.vue` | 历史参数管理，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/pages/admin/users.vue` | 历史用户管理，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/pages/index/index.vue` | 历史首页，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/pages/login/login.vue` | 历史登录页，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/pages/my/my.vue` | 历史个人中心，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/pages/register/register.vue` | 历史注册页，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/pages/reserve/reserve.vue` | 历史预约页，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/pages/room/room.vue` | 历史房间详情，单文件组件中包含页面结构、逻辑和样式，仅供参考。 |
| `frontend/scripts/uni.cjs` | 历史 uni-app 开发和编译命令包装。 |
| `frontend/static/logo.png` | 历史前端 Logo。 |
| `frontend/static/tab-home-active.png` | 历史首页选中状态图标。 |
| `frontend/static/tab-home.png` | 历史首页底部图标。 |
| `frontend/static/tab-my-active.png` | 历史我的选中状态图标。 |
| `frontend/static/tab-my.png` | 历史我的底部图标。 |
| `frontend/store/user.js` | 历史前端用户和登录状态管理。 |
| `frontend/uni.scss` | 历史前端公共样式变量。 |
| `frontend/vite.config.cjs` | 历史前端 Vite 构建配置。 |

## cloudfunctions/历史参考云函数

| 文件 | 用途 |
|---|---|
| `cloudfunctions/admin/index.js` | 第一版管理接口的云函数代码，仅作历史参考，正式 v2 不调用它。 |
| `cloudfunctions/admin/package-lock.json` | 锁定该历史云函数的依赖版本。 |
| `cloudfunctions/admin/package.json` | 该历史云函数的依赖与包配置。 |
| `cloudfunctions/auth/index.js` | 第一版账号认证的云函数代码，仅作历史参考，正式 v2 不调用它。 |
| `cloudfunctions/auth/package.json` | 该历史云函数的依赖与包配置。 |
| `cloudfunctions/messages/index.js` | 第一版空间留言的云函数代码，仅作历史参考，正式 v2 不调用它。 |
| `cloudfunctions/messages/package.json` | 该历史云函数的依赖与包配置。 |
| `cloudfunctions/reservations/index.js` | 第一版预约业务的云函数代码，仅作历史参考，正式 v2 不调用它。 |
| `cloudfunctions/reservations/package.json` | 该历史云函数的依赖与包配置。 |
| `cloudfunctions/rooms/index.js` | 第一版房间查询的云函数代码，仅作历史参考，正式 v2 不调用它。 |
| `cloudfunctions/rooms/package.json` | 该历史云函数的依赖与包配置。 |
| `cloudfunctions/seed/index.js` | 第一版云端初始化的云函数代码，仅作历史参考，正式 v2 不调用它。 |
| `cloudfunctions/seed/package-lock.json` | 锁定该历史云函数的依赖版本。 |
| `cloudfunctions/seed/package.json` | 该历史云函数的依赖与包配置。 |

## 本地会出现、但不逐文件提交的目录

| 路径 | 用途与注意事项 |
|---|---|
| `.git/` | Git版本历史、分支和远程配置；内部由Git维护 |
| `.venv/` | Python依赖环境；换电脑应按requirements.txt重建 |
| `backend/.env` | 当前机器后端真实配置，可含AppSecret和数据库密码；不提交Git |
| 根目录 `.env`（按部署需要建立） | Docker Compose读取的变量；backend/.env不会自动变成根目录Compose配置 |
| `backend/shuyuan.db` | 本地SQLite数据库，含运行数据；不作为源码交付，生产使用PostgreSQL |
| `backend/uploads/` | 公开留言图片运行目录 |
| `backend/private_uploads/` | 玉兰卡/清扫等私密照片运行目录，访问须鉴权 |
| `dist/miniprogram-development/` | 开发构建产物，内部有小程序、项目配置和构建清单 |
| `dist/miniprogram-staging/` | 执行体验环境构建后生成的产物 |
| `dist/miniprogram-production/` | 执行正式构建后生成的产物，要求正式AppID和HTTPS地址 |
| `node_modules/` | Node第三方依赖；出现在相应历史项目中，不能把它当业务源码逐个修改 |
| `__pycache__/`、`.pytest_cache/` | Python与测试缓存，可重建，不提交 |
| `project.private.config.json` | 开发者工具本机个性化配置，不应拿它当共享项目配置 |
| `frontend/dist/`、`frontend/unpackage/`、`frontend/.uni-src/` | 历史前端构建或临时产物，不是正式原生小程序入口 |

## 按修改目标找文件

| 目标 | 优先找哪里 |
|---|---|
| 修改页面文字/结构/颜色 | 对应pages目录的wxml/wxss，公共样式在app.wxss |
| 修改页面按钮行为或请求 | 对应页面js；公共请求在utils/api.js |
| 新增页面 | pages中创建四类文件，再登记app.json |
| 修改AppID | 根目录project.config.json；构建产物通过MINIPROGRAM_APP_ID注入 |
| 修改后端地址 | 源码开发默认在build.config.js；构建通过MINIPROGRAM_API_BASE_URL注入 |
| 配置AppSecret | 学校服务器受控环境变量WECHAT_APP_SECRET，不写入前端 |
| 修改业务规则 | 后台配置可调参数；复杂行为改backend/app/domain/对应模块 |
| 新增接口 | routers解析输入和鉴权，domain实现业务，schemas定义契约 |
| 改数据库字段 | models与Alembic迁移一起改，不只改数据库文件 |
| 找部署/故障说明 | docker-compose.yml、deploy/、docs/OPERATIONS_RUNBOOK.md |
| 核对交付是否完成 | docs/RELEASE_CHECKLIST.md及相应测试、验收证据 |

## 一个预约请求经过哪些文件

`reserve.js` 选时段 → `form.js` 收集表单 → `app.js` / `utils/api.js` 发请求 → `backend/app/main.py` 注册的 `routers/reservations.py` 接口 → `schemas.py`校验 → `domain/reservations.py`检查与分房 → `models.py` / `database.py`写入数据库 → 结果回到页面。

审核从 `admin.js` 发起，由 `routers/admin.py` 调用 `domain/reviews.py`；通知入队后由 `worker.py` → `tasks.py` → `notifications.py`投递。前端显示按钮只是交互，最终权限和规则始终由后端判断。
