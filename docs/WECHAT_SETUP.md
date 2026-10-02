# 微信平台、构建与真机联调

2026-10-02候选源码。AppID已有配置，成员权限、学校密钥、模板、真实域名及发布仍须小程序管理员确认。构建命令见 [跨平台构建与校验](BUILD_ARTIFACT_GUIDE.md)，服务器首次部署见 [部署教程](DEPLOYMENT_GUIDE.md)。

## 正确的导入目录

```text
DUT-duxue-space-booking/
├── project.config.json   本地源码项目配置
├── miniprogram/          正式原生微信前端
├── backend/              FastAPI主后端
├── frontend/             历史参考
└── cloudfunctions/       第一版参考
```

本地源码调试导入仓库根目录，`miniprogramRoot`为`miniprogram/`。`npm run build:dev`产物也可单独导入`dist/miniprogram-development/`。体验/正式版本分别导入`dist/miniprogram-staging/`、`dist/miniprogram-production/`，不能上传源码根目录替代已经注入正式参数的产物。主线不需要uni-app编译或微信云函数部署。

## 本地模拟器

按 [README快速启动](../README.md#本地演示启动) 在Windows/macOS/Linux启动本地API和需要时的worker；seed及`admin001/admin123`仅用于虚构数据演示。

开发者工具导入源码根目录→本地设置临时关闭合法域名校验→编译→登录演示账号。默认请求`http://127.0.0.1:8000/api`，仅同电脑模拟器可用；手机127.0.0.1指手机自身。

开发构建可在控制台临时覆盖API：

```js
wx.setStorageSync('apiBaseUrl', 'https://学校实际API域名/api')
```

体验/正式构建禁止这个覆盖。发布地址由MINIPROGRAM_API_BASE_URL注入，无需手改config.js；根配置不会被构建修改。

## AppID、权限与AppSecret

根`project.config.json`当前AppID为`wx78c441ce72d765fc`。开发构建优先环境变量MINIPROGRAM_APP_ID，未提供回退根值；production必须显式提供有效值，不回退。学校须在 [微信公众平台](https://mp.weixin.qq.com/) 确认属于正确主体，并将实际开发者和体验人员加入项目，配置正确不等于权限已确认。

由小程序管理员在公众平台小程序的开发管理/开发设置相关页面查找AppID/AppSecret（具体栏目以当前后台为准）；密钥生成/重置需要相应管理员权限与平台验证，开发者绑定不保证可查看密钥。无法查看时由学校管理员处理，不在前端尝试推导。

AppSecret用于后端调用微信接口，包括换取OpenID和消息所需access token；不是上传前端代码的密码。它会在重置/轮换时改变，不是永久不变。学校将真实密钥放入受控服务器环境，更新API和worker配置并使新环境生效，再复核绑定/消息。微信平台当前界面和校验要求需管理员实际确认；本文未对学校后台执行操作。

## 后端变量放在哪里

| 运行方式 | 配置来源 | 操作要求 |
|---|---|---|
| 直接Python | 从backend工作目录读取backend/.env，或服务进程环境 | 参照backend/.env.example，文件仅服务账号/运维可读 |
| Compose | 根.env或明确--env-file，用于Compose插值 | 参照根.env.example；backend/.env不会自动读取，API与worker均注入 |

```env
WECHAT_APP_ID=wx78c441ce72d765fc
WECHAT_APP_SECRET=
WECHAT_TEMPLATE_SUBMITTED=
WECHAT_TEMPLATE_REVIEW=
WECHAT_TEMPLATE_REMINDER=
WECHAT_TEMPLATE_RESTRICTION=
```

这是空密钥模板，不含真实AppSecret。后端AppID必须与目标产物一致。真实.env、AppSecret、access token不放在miniprogram、Git、截图、群聊或教程正文。Compose改配置后使用`docker compose up -d --force-recreate api worker`使新环境生效，仅restart不更新已有容器环境；数据库密码另按运行手册处理。

## 模板、合法域名与隐私

小程序管理员申请四类订阅消息模板并核对实际字段，代码映射在`backend/app/notifications.py`：

| 业务 | 当前字段 |
|---|---|
| 提交成功 | thing1房间、time2日期时段 |
| 审核结果 | phrase1结果、thing2备注 |
| 开始提醒 | thing1提示、time2日期 |
| 资格变更 | thing1变更、thing2原因 |

若实际模板字段不同，维护者需同步`_template_data()`，只填模板ID不会自动适配。学校要实际验证字段长度、内容和消息成功/失败路径。

学校部署受信任HTTPS，例如`https://space-api.example.edu.cn`，nginx代理/api和受限公开/uploads，私密图片经/api/media鉴权。公众平台将实际域名加入request、uploadFile、downloadFile合法域名，确认证书/DNS/端口；不能仅靠开发工具关闭校验替代真机验证。正式示例域名须替换。

小程序管理员与隐私负责人填写姓名、学号、手机号、玉兰卡/清扫照片的用途、访问与保留期限；代码默认私密图90天清理，学校需书面确认。不把自填学号当作学校身份认证。

## 构建、上传体验版与发布责任

1. 运维完成服务器ready与HTTPS，业务负责人核对基础数据/正式账号。
2. 维护者取得已审核目标提交，按 [构建指南](BUILD_ARTIFACT_GUIDE.md) 在Windows或macOS/Linux注入MINIPROGRAM_API_BASE_URL、MINIPROGRAM_APP_ID、RELEASE_VERSION、GIT_COMMIT，构建并校验文件清单/摘要。
3. 开发者导入目标dist目录，核对AppID、API、版本和提交；开发者工具用已绑定的微信账号登录、编译并按工具提示上传版本/说明。
4. 小程序管理员在公众平台选择上传版本作为体验版本、登记体验成员，学校用真实iPhone/Android完成下列清单，留存脱敏证据。
5. 业务/运维/隐私/维护者按既有 [发布清单](RELEASE_CHECKLIST.md) 完成签字，小程序管理员按公众平台流程提交审核、处理反馈和发布。

上传代码到微信只交付前端；数据库/API/照片仍在学校服务器。源码ZIP、GitHub链接和dist构建包都不会自动成为微信可用的正式应用。平台审核与服务器可用性分别验收。

## 真实绑定与消息流程

密码登录/注册后调用wx.login，后端用AppID/AppSecret交换OpenID并绑定当前账号；无本地有效token时可按已有绑定尝试微信登录。模板配置读取后，由本人wx.requestSubscribeMessage授权。预约/审核/限制事件进入outbox，由独立worker发送。

拒绝授权、配置缺失、微信接口失败不应回滚已成功预约。“我的→消息记录与发送状态”能查看记录，真实发送仍需平台联调。人工密码恢复成功会撤销旧会话与微信绑定；重新密码登录后重绑。辅导员首次强制改密流程见 [使用教程](USER_GUIDE.md)。没有短信验证码服务，人工本人核验须学校制定流程。

## 学校真机验收清单

- [ ] 主体/AppID/开发者/体验权限核对；产物与后端AppID、版本/提交一致。
- [ ] iPhone/Android注册、密码登录、退出/过期、人工恢复、辅导员首次换密、微信重绑。
- [ ] 空间导览、四场景分配、用途/人数/连续时段和限制提示；可信身份方案另行确认。
- [ ] 审核/取消/签到码、照片上传/失败重试、清扫通过/退回及重传、每日额度。
- [ ] 全部订单、违规待办、区间禁约/解除、操作日志、Excel与鉴权照片链接。
- [ ] 四类消息成功、拒绝授权、接口失败与补偿；核对消息记录并确认业务不回滚。
- [ ] Wi-Fi/移动网络/弱网、长列表/键盘/安全区域、照片预览/Excel打开、无障碍操作。
- [ ] HTTPS续期、API/worker重启持久化、备份恢复及运维独立执行教程。
- [ ] 隐私说明、保留/删除、身份核验、反馈联系人和维护期限签字。

本地自动测试或临时容器结果不勾选这份真实学校清单；状态见 [05–11验证记录](HANDOVER_DOCUMENTATION_REPORT.md)。
