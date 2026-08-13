# 微信平台、真机与学校服务器联调清单

## 先确认正确的项目入口

正式微信前端是根目录下的 `miniprogram/` 原生小程序。微信开发者工具应直接导入仓库根目录：

```text
书院空间预约制度/
├── project.config.json     ← 开发者工具读取
├── miniprogram/            ← 正式 v2 小程序
├── backend/                ← FastAPI
├── frontend/               ← 仅参考，不导入
└── cloudfunctions/         ← 第一版参考，不是 v2 主后端
```

根目录 `project.config.json` 已配置 `"miniprogramRoot": "miniprogram/"`。不要导入 `frontend/dist/`，也不需要为正式 v2 编译 uni-app。

## 本地模拟器联调

先启动后端：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe seed.py
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

然后在微信开发者工具中：

1. 导入仓库根目录。
2. 在“本地设置”中临时关闭合法域名校验。
3. 编译小程序。
4. 使用 `admin001 / admin123` 或测试学生账号联调。

`miniprogram/config.js` 的默认地址是：

```js
http://127.0.0.1:8000/api
```

这个地址只适用于运行在同一台电脑上的微信开发者工具模拟器。手机中的 `127.0.0.1` 指向手机自身，不会访问开发电脑，因此不能把它用于真机验收或生产发布。

开发阶段也可在开发者工具控制台临时覆盖地址：

```js
wx.setStorageSync('apiBaseUrl', 'https://学校正式域名/api')
```

这只是本机调试覆盖；发布版本仍应把 `miniprogram/config.js` 的默认地址改成学校 HTTPS API 地址。

## 必须由用户或学校在微信公众平台完成的事项

以下事项不能由代码自动代办：

| 事项 | 操作人 | 结果/需交给开发的信息 |
|---|---|---|
| 注册并认证小程序主体 | 书院/学校管理员 | 正式 AppID |
| 添加项目开发者、体验成员 | 小程序管理员 | 开发和验收账号获得权限 |
| 生成并保管 AppSecret | 小程序管理员/学校运维 | 仅写服务器环境变量，不发到聊天或 Git |
| 申请订阅消息模板 | 小程序管理员 | 四个模板 ID 及关键词字段顺序 |
| 配置服务器合法域名 | 小程序管理员 | request、uploadFile、downloadFile 域名通过校验 |
| 配置隐私保护指引 | 小程序管理员与业务负责人 | 说明姓名、学号、手机号、玉兰卡和清扫照片用途/保存期限 |
| 上传体验版、提交审核和发布 | 小程序管理员 | 完成校内验收后上线 |

公众平台界面和审核要求可能调整，实际操作以届时平台提示为准。

## AppID、AppSecret 和模板 ID 放在哪里

### 小程序 AppID

填入根目录 `project.config.json`：

```json
{
  "appid": "学校正式小程序AppID"
}
```

### 服务器微信配置

AppID、AppSecret 和模板 ID 只写学校服务器的 `backend/.env`：

```env
WECHAT_APP_ID=
WECHAT_APP_SECRET=
WECHAT_TEMPLATE_SUBMITTED=
WECHAT_TEMPLATE_REVIEW=
WECHAT_TEMPLATE_REMINDER=
WECHAT_TEMPLATE_RESTRICTION=
```

`WECHAT_APP_ID` 必须与 `project.config.json` 使用同一个小程序。真实 `.env` 不得提交到 Git。AppSecret 不应放入 `miniprogram/`、截图、群聊或交接文档正文。

当前模板数据映射位于 `backend/app/notifications.py`：

- 提交成功：`thing1`（房间）、`time2`（日期时段）
- 审核结果：`phrase1`（结果）、`thing2`（备注）
- 临近开始：`thing1`（提示）、`time2`（日期）
- 预约资格变更：`thing1`（变更）、`thing2`（原因）

如果公众平台最终选中的模板字段编号不同，开发人员必须同步修改 `_template_data()`；仅把不匹配的模板 ID 填入 `.env` 不会自动适配字段。

## 真机和生产域名

学校需准备类似下面的正式地址：

```text
https://space-api.example.edu.cn
```

要求和配置点：

1. 使用受信任的 HTTPS 证书；不要以 `127.0.0.1`、`localhost`、裸 IP 或自签名证书作为正式地址。
2. nginx 将 `/api/` 与公开留言图片的 `/uploads/` 转发到 FastAPI；私密媒体只允许通过 `/api/media/{media_id}` 鉴权下载。
3. 设置 `MINIPROGRAM_API_BASE_URL=https://space-api.example.edu.cn/api` 和正式 `MINIPROGRAM_APP_ID` 后执行 `npm run build:prod`，不要手工修改源码。
4. 在微信公众平台把 `https://space-api.example.edu.cn` 加入：
   - request 合法域名；
   - uploadFile 合法域名；
   - downloadFile 合法域名。
5. 真机联调前重新编译并上传体验版；不能只关闭开发者工具中的域名校验。

## 订阅消息实际流程

学生提交预约或在“我的”开启通知时，小程序会：

1. 调用 `wx.login` 获取临时代码；
2. 由后端使用 AppID/AppSecret 换取 OpenID 并绑定当前账号；
3. 获取服务器已配置的模板 ID；
4. 调用 `wx.requestSubscribeMessage` 由学生本人选择是否授权；
5. 后端把业务事件写入 outbox，再由定时任务发送。

用户拒绝授权、微信配置为空或消息接口暂时失败，都不应回滚预约。未配置模板时只能验收预约业务，不能宣称真实订阅消息已完成。

## 短信找回密码现状

短信验证码找回尚未接入 FastAPI，也没有可用的学校短信供应商配置。当前 `pages/login/forgot` 只提示学生联系辅导员或书院管理员核验身份。

因此上线前需在以下方案中由学校确认一种：

- 接入学校统一身份认证并由统一平台重置；
- 接入学校已有短信服务，新增验证码发送、过期、频率限制和重置接口；
- 保留人工核验重置，并制定管理员操作流程。

在方案确认并实现前，不应把第一版云函数中的短信占位符当作可用功能。

## 学校服务器交接清单

学校运维需要接收并确认：

- Linux/容器运行环境、正式 DNS、HTTPS 证书和端口策略；
- PostgreSQL 地址、最小权限账号、备份频率和恢复演练；
- 强随机 `SECRET_KEY`、微信 AppSecret、模板 ID 的安全注入方式；
- `UPLOAD_DIR`（留言图）与 `PRIVATE_UPLOAD_DIR`（敏感图）的隔离持久化、备份和到期清理策略；
- nginx 对 `/api/`、`/uploads/` 的代理与上传大小限制；
- FastAPI 服务的开机启动、健康检查、日志轮转和告警；
- 独立 worker 由 PostgreSQL advisory lock 选出当前执行者；可部署备用实例，但不得让 API 进程运行内置调度器；
- 替换默认管理员凭据，并保管管理员账号；
- 辅导员 CSV 的授权来源和安全导入流程；
- 数据保留、用户注销、隐私投诉和安全事件联系人。

建议学校运维与书院业务老师共同保存一份不含明文密钥的配置清单，真实密钥通过学校密码库或受控渠道交接。

## 上线前验收顺序

1. 学生注册、登录、退出和 token 失效处理。
2. 空间导览、房间详情和公开空间状态。
3. 四场景可用性、连续时段、自动分房和玉兰卡上传。
4. 管理员审核、学生取消、签到与扫码签到。
5. 使用结束、清扫照片上传、复核通过/退回和再次预约阻断。
6. 违约累计、自动限制、人工限制与解除。
7. 按条件 Excel 下载、签到二维码生成/预览和系统参数/分房规则修改。
8. 真机 OpenID 绑定、订阅授权和四类消息发送。
9. 隐私提示、弱网、上传超限、服务器重启和备份恢复。

辅导员 CSV 已可由原生管理页选择微信文件上传；验收时应同时确认新账号凭据只保存到学校受控文档。短信找回仍不在当前已完成范围内。
