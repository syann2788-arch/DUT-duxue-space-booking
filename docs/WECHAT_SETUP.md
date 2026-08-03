# 微信平台联调清单（你需要配合的部分）

代码本地验收不需要微信云开发，也不需要现在购买腾讯云资源。要在真实微信中使用时，按以下顺序配合。

## 1. 注册并认证小程序

1. 在 [微信公众平台](https://mp.weixin.qq.com/) 注册“小程序”账号，主体建议使用学校/学院组织主体。
2. 完成管理员绑定与主体认证，取得 AppID。
3. 把 AppID 填入 `frontend/manifest.json` 的 `mp-weixin.appid`。
4. AppSecret 只填学校服务器的 `backend/.env`：`WECHAT_APP_SECRET=...`。不要发到聊天、前端代码或 Git。

## 2. 准备学校 HTTPS 地址

向学校信息化/网络部门申请类似：

- API 域名：`https://space-api.example.edu.cn`
- 有效公网 HTTPS 证书（不能只用 IP 或自签名证书）
- PostgreSQL 数据库及备份策略
- 持久化照片目录或学校对象存储

拿到域名后，将 `frontend/.env` 设置为：

```env
VITE_API_BASE_URL=https://space-api.example.edu.cn/api
```

## 3. 配置服务器域名

登录微信公众平台，在开发设置的服务器域名中，把同一个 HTTPS 域名加入：

- `request` 合法域名
- `uploadFile` 合法域名
- `downloadFile` 合法域名（查看/下载照片时使用）

微信开发者工具本地调试可临时关闭域名校验；发布前必须打开并使用已备案的 HTTPS 域名。微信小程序只会向配置过的服务器域名发起网络请求。[微信网络能力文档](https://developers.weixin.qq.com/miniprogram/dev/framework/ability/network.html)

## 4. 申请订阅消息模板

在公众平台“订阅消息”中申请四类一次性订阅模板，并把模板 ID 填入服务器 `.env`：

```env
WECHAT_TEMPLATE_SUBMITTED=
WECHAT_TEMPLATE_REVIEW=
WECHAT_TEMPLATE_REMINDER=
WECHAT_TEMPLATE_RESTRICTION=
```

当前发送器使用的关键词字段为：

- 提交成功：`thing1`（房间）、`time2`（日期时段）
- 审核结果：`phrase1`（结果）、`thing2`（备注）
- 临近开始：`thing1`（提示）、`time2`（日期）
- 账号限制：`thing1`（变更）、`thing2`（原因）

申请模板时字段类型/序号必须一致；若公众平台提供的模板序号不同，只需调整 `backend/app/notifications.py` 的 `_template_data()` 映射。学生每次提交前，小程序会调用 `wx.requestSubscribeMessage` 请求一次授权；拒绝授权不会阻止预约。[微信发送订阅消息文档](https://developers.weixin.qq.com/miniprogram/dev/OpenApiDoc/mp-message-management/subscribe-message/sendMessage.html)

## 5. 最后联调与发布

1. 学校服务器填写 `.env`，启动 PostgreSQL、FastAPI、nginx。
2. 运行 `python seed.py`，登录后修改/替换默认管理员密码。
3. 在微信开发者工具测试：登录绑定、提交、管理员审批、消息、签到、照片上传/复核、Excel。
4. 上传体验版，让书院老师用管理员/学生两个账号验收。
5. 补充隐私保护指引（收集姓名、学号、手机号、现场照片的用途与保存期限），再提交微信审核。

你需要提供给开发联调的信息只有：AppID、已经选好的四个模板 ID、最终 API 域名。AppSecret 应由学校运维人员直接写入服务器，不必提供给开发聊天。
