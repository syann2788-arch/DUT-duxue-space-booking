# 学校源码交付与接收指南

适用于当前`0.1.0-rc.1`源码候选交付。两份ZIP足以交接代码和教程材料；学校可用的小程序还须部署服务器、配置微信、真机验收和签字。发布条件见 [阶段清单](RELEASE_CHECKLIST.md)。本地打包命令不发布；经授权推送rc标签后，Quality Gate全部五项检查成功才自动创建候选GitHub Release和上传四份附件。微信发布仍由小程序管理员操作。

## 1. 交付物清单

| 文件/材料 | 用途与接收方 |
|---|---|
| `source.zip` | 固定Git提交的完整源码，解压得到source/；开发/服务器运维使用。含正式miniprogram、backend与迁移、测试、脚本、教程，历史frontend/cloudfunctions标明参考。 |
| `handover.zip` | 候选交付合集，含同一份source.zip、教程副本/模板、START_HERE、状态记录、接收登记和可选微信构建包。不是可直接安装到微信的应用。 |
| `handover-manifest.json` | 版本、完整提交、标签（未创建时null）、阶段、逐文件长度/SHA-256和两份ZIP摘要；不声称自动部署或已签字。 |
| `SHA256SUMS` | 两份ZIP、manifest及可选构建ZIP的校验值；通过独立可信渠道确认，不能只靠同一下载中的散列证明来源可信。 |
| `miniprogram.zip`（可选） | production构建目录，仍须微信开发者工具导入、上传体验/正式版本；服务器程序不上传微信。 |
| 使用/部署/微信/备份恢复教程 | 源码内docs/及交付合集均提供；从README按角色进入。 |
| 测试、已知限制、配置模板 | 同提交内的报告、需求对照/路线图、根/后端.env.example与部署模板。历史测试保留轮次，最终CI以随交付登记的目标运行链接为准。 |

禁止把真实`.env`、AppSecret、数据库、公开/私密业务照片、真实人员CSV、账号初始密码、访问令牌或备份装入ZIP。脚本拒绝相关路径、符号链接和子模块，只导出Git已提交内容；它不替代人工审查文件内容中的秘密或权利。虚构`*.example.csv`和配置模板允许交付。没有把缓存、node_modules、.venv或dist放进源码包。

## 2. 本地预检包与已批准候选包

下列从仓库根目录执行，需要Git、Python3.12+，可选微信构建还需Node22。

macOS/Linux：

```sh
npm test
npm run release:check -- --candidate
python3 scripts/test_handover_package.py
python3 scripts/check-handover-docs.py
# 先提交本轮代码与教程；打包拒绝不干净工作区
python3 scripts/package_handover.py pack --ref HEAD --draft
```

Windows PowerShell：

```powershell
npm test
npm run release:check -- --candidate
python scripts/test_handover_package.py
python scripts/check-handover-docs.py
# 提交完成后
python scripts/package_handover.py pack --ref HEAD --draft
```

默认输出`dist/handover/<版本>-<提交前12位>/`，同路径存在时拒绝覆盖。`--draft`仅供尚未进入main的改动预检，记录draft-before-main-review；版本号不是“标签已存在”的证明。输出不包含未提交文件；Git被忽略的真实配置不会读取。

维护者确认候选交付、固定提交已入main并且目标CI通过后，先刷新远程引用，用完整提交或不可变标签重新打包，**不加draft**：

```sh
git fetch origin
# 将占位内容替换为实际已批准完整提交
python3 scripts/package_handover.py pack --ref 完整提交 --output dist/handover/approved-candidate
python3 scripts/package_handover.py verify dist/handover/approved-candidate
```

非draft会核对目标提交属于origin/main，版本必须rc；若同版本标签已存在，须指向同一提交，否则拒绝。main包含某提交不证明该提交CI/审批成功，这些仍由维护者登记。正式上线在稳定版本和全部验收齐备后，可用`pack --kind production --acceptance /受控路径/acceptance.json --miniprogram`；production不能draft，必须有真实脱敏截图、完整验收记录及正确微信配置。脚本检查验收结构完整性，发布负责人核对原件。

## 3. 可选微信构建

学校API地址缺失时交源码和教程，接收方之后从固定源码构建；不要用占位域名冒充学校配置。具备实际配置后：

```sh
MINIPROGRAM_APP_ID=wx78c441ce72d765fc \
MINIPROGRAM_API_BASE_URL=https://学校实际域名/api \
python3 scripts/package_handover.py pack --ref 完整提交 --output dist/handover/configured-candidate --miniprogram
```

PowerShell先设`$env:MINIPROGRAM_APP_ID`和`$env:MINIPROGRAM_API_BASE_URL`，再用`python`执行同样命令。AppSecret不提供给构建脚本。打包在临时目录从目标Git树构建，自动注入该提交/版本，产物清单createdAt取提交时间以保证同输入重复摘要；不会修改本地miniprogram源码。自动核对构建清单、版本/提交与源码文件清单，合并进handover.zip并另附miniprogram.zip。

## 4. 接收、解压和校验

1. 接收两份ZIP、manifest和SHA256SUMS，独立核对维护者提供的版本/完整提交与SHA256SUMS。下载分支网页ZIP可能不含固定说明或正式构建，因此固定发行附件与校验记录更适合存档。
2. 解压source.zip得到source/；其中已有校验脚本，无需安装Python第三方库。把外层文件保留在同一目录，不混放额外文件。
3. 执行`python3 source/scripts/package_handover.py verify 外层目录`（Windows用python）。检查缺失、新增、修改、重复/不安全ZIP成员，以及教程/内嵌源码与外层源码是否一致。若有微信包还需Node。
4. 校验通过后阅读source/README.md。解压handover.zip，按START_HERE阅读教程与填写HANDOVER_RECEIPT.md；所有真实联系人信息、维护期限和签字由双方填写，空表不代表已交付。
5. 服务器运维按 [部署教程](DEPLOYMENT_GUIDE.md)创建运行环境、PostgreSQL、迁移、基础房间/规则、正式账号、API/worker和HTTPS；不能在学校生产库用seed演示账号。
6. 小程序管理员按 [微信教程](WECHAT_SETUP.md)核对AppID主体/成员权限、合法域名、学校注入后端的AppSecret/模板；从固定源码构建或导入附带构建目录，完成体验和真机验收。
7. 学生/辅导员/管理员按 [使用教程](USER_GUIDE.md)完成一次主链路；学校运维按 [运维手册](OPERATIONS_RUNBOOK.md)独立进行备份恢复。按阶段清单记录签字。

校验报告只证明收到的文件与清单一致，不证明学校资源、身份验证、审批或许可证已完成。修改任一交付物后校验失败，应重新从新提交打包，不能在旧包里手改后沿用旧标签。

## 5. 单独受控交接与责任登记

AppSecret、强随机SECRET_KEY、数据库密码、管理员/辅导员初始密码、恢复凭证、真实人员CSV、业务数据库/照片、加密私钥及备份在学校密码库或授权渠道交接，ZIP和公开Release不包含这些内容。登记交接记录编号即可，不在公开登记表粘贴秘密。

至少约定学校业务负责人、服务器运维、小程序管理员、数据/隐私负责人、源码维护方；确认维护截止日期、缺陷修复范围、后续需求费用/流程、密钥轮换与备份责任。维护期限不能由开发方自行填成永久。接收源码的日期和学校验收日期分别记录。

## 6. GitHub发布顺序

工具/文档PR合入main → 最新main五项CI成功 → 确认本次候选预发布及公开范围 → 同步版本/CHANGELOG → `release:check --candidate --tag` → 新建不可变rc标签 → 标签CI五项检查成功 → Publish candidate Release作业从该标签重新打包/核对，先上传四份附件到草稿，全部确认后公开为“待部署验收”pre-release → 学校接收/部署 → 联合验收签字 → 稳定版本正式发布。

Release附件是source.zip、handover.zip、handover-manifest.json和SHA256SUMS。Packages用于Docker/npm等软件包，本次源码ZIP交付无需发布Packages。已存在的Release拒绝覆盖；上传失败只清理本次尚未公开的草稿，不删除已公开版本。本地生成ZIP不会建立远程标签或Release。正式版本不自动发布，仍执行production检查与受控验收记录，保留全部学校门槛。
