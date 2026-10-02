# 小程序构建与产物校验

适用日期：2026-10-02。以下命令均从仓库根目录执行，使用 Node.js 22（与 CI 一致）。构建不需要 Docker，不修改源码；输出在 `dist/`，不会提交到 Git。

## 开发构建与 AppID

```sh
npm run build:dev
node scripts/verify-miniprogram-build.mjs dist/miniprogram-development
```

开发构建优先使用环境变量 `MINIPROGRAM_APP_ID`，未提供时回退到根目录 `project.config.json`。当前根配置是 `wx78c441ce72d765fc`。API 默认 `http://127.0.0.1:8000/api`，允许开发阶段的本地存储覆盖。微信开发者工具可导入源码根目录，或导入 `dist/miniprogram-development/`。

AppID 的格式或文件配置正确，只证明配置有效；微信成员权限、学校主体和后台配置仍需学校确认。AppSecret 只注入后端，不参与前端构建。

## 体验与正式构建

环境变量只作用于构建时生成的产物，根配置与源码 `build.config.js` 不会被覆盖。

| 参数 | development | staging | production |
|---|---|---|---|
| `MINIPROGRAM_API_BASE_URL` | 可省略，默认本地 API | 必须提供 | 必须提供，以 `/api` 结尾的 HTTPS，拒绝本地/局域网地址 |
| `MINIPROGRAM_APP_ID` | 可省略，回退根 AppID | 应显式提供；当前无正式格式门禁 | 必须显式提供，格式为 `wx` 加16位十六进制字符；不回退根 AppID |
| `RELEASE_VERSION` | 可省略，记为 `unreleased` | 可省略，记为 `unreleased` | 必须提供版本号，例如 `v0.1.0-rc.1` 或 `1.0.0` |
| `GIT_COMMIT` | 可省略，记为 `unknown` | 可省略，记为 `unknown` | 必须提供完整40或64位十六进制提交编号，拒绝短编号和 `unknown` |
| API 本地存储覆盖 | 允许 | 禁止 | 禁止 |

学校体验验收也应显式提供四项参数，并使用学校 HTTPS 地址。脚本的严格生产门禁仅在 `build:prod` 生效。

下面的域名和版本仅是命令示例，应替换为经确认的目标域名与版本。正式交付前，按现有发布清单在已审核、无未提交修改的目标提交上构建，并确认版本标签指向该提交。脚本校验提交编号格式，**不会自动证明工作区内容属于该提交或版本标签**；从源码 ZIP 重建时，提交编号应取自随包交付的版本记录。

macOS/Linux：

```sh
export MINIPROGRAM_API_BASE_URL='https://space-api.example.edu.cn/api'
export MINIPROGRAM_APP_ID='wx78c441ce72d765fc'
export RELEASE_VERSION='v0.1.0-rc.1'
export GIT_COMMIT="$(git rev-parse HEAD)"
npm run build:prod
node scripts/verify-miniprogram-build.mjs dist/miniprogram-production
```

Windows PowerShell：

```powershell
$env:MINIPROGRAM_API_BASE_URL = 'https://space-api.example.edu.cn/api'
$env:MINIPROGRAM_APP_ID = 'wx78c441ce72d765fc'
$env:RELEASE_VERSION = 'v0.1.0-rc.1'
$env:GIT_COMMIT = (git rev-parse HEAD).Trim()
npm run build:prod
node scripts/verify-miniprogram-build.mjs dist/miniprogram-production
```

体验构建使用同样变量，把最后两条命令换为 `npm run build:staging` 和 `node scripts/verify-miniprogram-build.mjs dist/miniprogram-staging`。正式配置缺失或不合法时，构建报错且保留原有输出目录。成功后导入对应 `dist/miniprogram-production/` 或 `dist/miniprogram-staging/`，核对产物的 AppID、API 地址和版本，再按 [微信联调清单](WECHAT_SETUP.md) 操作。构建目录仍需通过微信开发者工具上传、审核和发布。

## 清单与摘要含义

产物根目录包含 `project.config.json`、`miniprogram/` 和 `build-manifest.json`。清单采用 schemaVersion 2、SHA-256，并记录环境、版本、提交、AppID、API 和生成时间。

- `sourceFiles`：本次输入的整个 `miniprogram/` 加根 `project.config.json`，每个文件记录相对路径、字节长度和 SHA-256；不代表后端或整个源码 ZIP 的摘要。
- `sourceDigest`：上述完整源码清单按路径稳定排序后，对 UTF-8 编码的紧凑 JSON 计算 SHA-256。
- `files`：实际构建目录所有文件的同类清单，包含注入后的 `build.config.js` 与 `project.config.json`。
- `artifactDigest`：对排序后的 `files` 紧凑 JSON 计算 SHA-256。API、AppID、版本、提交或页面/工具/图片内容改变，摘要都会改变。

为避免循环计算，`files` 排除顶层 `build-manifest.json`；生成时间 `createdAt` 不进入聚合摘要。因此相同源码和相同构建参数重复构建，两个聚合摘要保持一致，清单时间可以不同。文件路径按字符串字典序稳定排序（JavaScript的UTF-16比较，不依赖系统语言），路径分隔符统一为 `/`，大小按字节计算。

校验命令会重新遍历实际产物，核对文件清单、每个文件大小/摘要和聚合摘要；缺失、新增、改动文件都会失败，并核对记录的源码清单与源码摘要是否一致。它不读取交付方原始源码，不能证明 Git 提交来源，也不是数字签名。应将清单与来自可信交付记录的版本/提交/摘要一起核对。

打包时保留构建根目录的清单，校验应在微信工具导入前执行，避免工具生成额外本地文件造成校验失败。源码 ZIP、完整交付包校验和、版本标签以及学校验收仍按 [发布清单](RELEASE_CHECKLIST.md) 完成。

## 本地复核

```sh
npm test
```

构建测试在临时目录覆盖默认/覆盖 AppID、正式参数门禁、源码不变、完整清单、重复稳定性、页面/工具/图片/文件增删与重命名、部署参数变化，以及产物篡改检测。GitHub 现有标签工作流继续使用标签名与 `github.sha` 注入正式版本和提交；构建后也执行校验。远程检查通过情况应以对应提交的实际 CI 记录为准。
