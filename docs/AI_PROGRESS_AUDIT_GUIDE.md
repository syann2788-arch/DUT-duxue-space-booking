# 给 AI 的小程序结构、GitHub 状态与开发进度检查指南

将下面内容交给有本地仓库及 GitHub 读取能力的 AI 执行。目标是检查并出具报告，不是直接改代码。报告必须基于检查时的真实状态，不能复用旧报告中的测试数字作为新结果。

## 任务与范围

请审计大连理工大学笃学书院空间预约小程序，回答：项目由哪些部分组成、哪些功能已经完成、GitHub 与本地是否一致、哪些工作阻碍试点或正式上线、接下来应优先做什么。

- 本地仓库：`/Users/liupengfei/little program/DUT-duxue-space-booking`
- 预期 GitHub 仓库：https://github.com/syann2788-arch/DUT-duxue-space-booking
- 先读取 `AGENTS.md`，用 `git remote -v` 核实远程地址；地址如有变化，以现场结果为准。
- 正式微信端为 `miniprogram/`，正式后端为 `backend/`（FastAPI）。`frontend/` 是 uni-app/H5 参考实现，`cloudfunctions/` 是第一版云开发参考。不要把参考实现的功能算成正式端已完成，也不要擅自改变主线。
- 只读检查；允许执行经过确认、使用隔离数据的测试。不得修改业务源码、提交、推送、合并 PR、创建 Release、部署、初始化现有数据库或操作真实用户数据。需要修复时先在报告中列出。
- 不输出密钥、token、真实个人信息、私密照片或完整生产环境配置；证据应脱敏。

## 一、建立检查基线

记录检查时间（Asia/Shanghai）、当前分支、HEAD SHA、工作区是否干净、远程地址和可用运行环境。读取 `README.md`、`ROADMAP.md`、`CHANGELOG.md`、`package.json`，以及：

- `docs/ARCHITECTURE.md`
- `docs/REQUIREMENTS_TRACEABILITY.md`
- `docs/LOCAL_COMPLETION_REPORT.md`
- `docs/PILOT_RELEASE_BASELINE.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/WECHAT_SETUP.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/GITHUB_ADMIN_SETUP.md`

区分“文档声称的状态”和“本次已验证的状态”。发现文档相互矛盾时，用源码和实测定位差异，不直接选择最乐观的声明。

建议先执行：

```bash
cd '/Users/liupengfei/little program/DUT-duxue-space-booking'
git status --short --branch
git remote -v
git rev-parse HEAD
git log -10 --date=iso --format='%h %ad %s'
rg --files -g '!node_modules' -g '!.venv' -g '!dist' -g '!build'
```

不要将当前父目录当成 Git 仓库。目录树应排除依赖、缓存、数据库、媒体和生成产物。

## 二、检查项目结构与真实调用链

给出简明目录树，为每个主要目录说明职责、入口、依赖关系、是否属于正式交付。重点检查：

1. `project.config.json` 的 `miniprogramRoot`、`miniprogram/app.json` 页面注册、页面文件是否齐全、页面入口是否可达。
2. `miniprogram/app.js`、`config.js`、`utils/api.js` 的登录态、请求地址、鉴权、错误处理和环境切换。
3. `backend/app/main.py` 的路由注册，以及 routers、domain、models、schemas、auth、database、config 的职责与调用关系。
4. 数据库迁移、独立 worker、消息队列、媒体权限与清理、健康检查的入口和部署方式。
5. `scripts/`、后端测试、`.github/workflows/quality.yml` 与部署文件如何验证和交付正式产品。
6. 重复实现、未使用页面、失效配置、占位代码、mock 数据、未接通接口、TODO/FIXME。搜索命中只是线索，要读上下文确认。

至少沿源码追踪一次“页面事件 → API 请求 → 路由 → 业务校验 → 数据持久化 → 页面结果”的预约链路，并检查身份与权限如何传递。不要仅凭文件存在判断功能完成。

## 三、逐项检查业务完成度

以需求对照表为起点，至少覆盖以下业务；如文档还有额外需求，一并纳入：

- 注册、登录、退出、微信绑定、学生/辅导员/管理员权限。
- 空间导览、房间详情、公开空间状态、A106 角色限制。
- 四种场景、连续半小时时段、自动分房、共享容量、独占及跨场景冲突。
- 单日预约时长、提前预约范围、取消截止、签到、二维码与防重复操作。
- 单条/批量审核、自动审批、预约状态自动推进。
- 玉兰卡照片、清扫上传、解锁与复核、私密媒体访问及保留期限。
- 违约累计、自动禁约、临时/限时/永久限制。
- 预约历史、后台列表、筛选、分页、导出、辅导员导入、后台配置。
- 使用者留言与照片、订阅消息授权、发送失败与重试。
- 网络异常、登录失效、弱网、重复点击、页面滚动与可访问性。

每项分别标注“实现状态”和“验证状态”：

- 实现状态：未实现 / 部分实现 / 已实现 / 无法确定。
- 验证状态：未验证 / 自动测试通过 / 本地联调通过 / 微信真机通过 / 生产等价环境通过。

表格列：需求、正式端入口、后端实现、测试或验收证据、实现状态、验证状态、缺口。证据尽量附文件与行号、测试名称或 GitHub 链接。区分现成能力、模拟成功、真实平台成功；不能把后端接口测试计为真机验收。

## 四、检查 GitHub 当前状态

通过 GitHub API、已登录的 `gh` 或可访问的网页获取当前记录；访问受限时明确说明范围，不能猜测远程状态。优先读取：

1. 默认分支及最新 commit SHA，与本地 HEAD 的关系。
2. 活跃分支、未合并 PR、近期已合并 PR；检查评审、冲突和检查结果。
3. 开放 Issues、里程碑、项目看板（如存在），识别 bug、验收项、阻断项及责任人。
4. Actions 最近运行及当前被检查 SHA 的运行结果；失败任务查看日志，区分代码失败、配置缺失与环境问题。
5. tags、Releases、发布说明及对应 SHA。tag 或 Release 存在不等于产品已上线。
6. 分支保护、必需检查与审批规则（权限允许时）；读不到设置应标“未验证”。

可使用：

```bash
gh auth status
gh repo view syann2788-arch/DUT-duxue-space-booking --json nameWithOwner,url,defaultBranchRef
gh pr list --repo syann2788-arch/DUT-duxue-space-booking --state open
gh issue list --repo syann2788-arch/DUT-duxue-space-booking --state open --limit 100
gh run list --repo syann2788-arch/DUT-duxue-space-booking --limit 20
gh release list --repo syann2788-arch/DUT-duxue-space-booking --limit 20
git ls-remote origin HEAD 'refs/heads/*' 'refs/tags/*'
```

检查分页，说明实际覆盖范围。不得因为开放 Issues 为零，就判断没有未完成工作；还需对照源码、路线图和验收清单。

用远程实时 SHA 判定同步状态。若远程跟踪分支未更新，不直接用旧 `origin/main` 判断领先/落后；需要精确比较时可把远程仓库克隆到临时目录，再比较提交图，不改变现有工作区。明确哪些变更仅在本地、哪些已推送、哪些已合并、哪些已有对应 CI 证据。

## 五、运行适当验证

先读测试配置和脚本，确认使用隔离数据库及临时目录，不会触达生产服务。依赖已有环境优先；缺失依赖或平台时记录限制，不为了检查擅自安装整套运行时或修改配置。

根目录的检查入口：

```bash
npm test
npm run release:check
```

后端使用已发现的 Python 虚拟环境，在 `backend/` 下运行：

```bash
python -m pytest -q
```

记录实际命令、运行环境、退出码、通过/失败/跳过数量和失败原因。区分本次执行、GitHub CI 执行、历史文档记录。测试跳过意味着该项未验证，不计为通过。

额外核查 PostgreSQL 并发测试是否真的运行、迁移版本是否匹配、API 与 worker 是否分别启动、CI 是否覆盖正式小程序与发布门禁。不要为验证而运行会建库写库的 seed、导入脚本或发布命令；不要使用 `release:check -- --tag` 替代普通进度检查。需要真机、微信凭据、学校服务器或生产等价数据库的项目，列为外部待验收项。

## 六、判断阶段与剩余工作

分别评价代码实现、本地验证、GitHub 集成、微信联调、校内试点、生产上线六个阶段，不用一个模糊“完成率”概括全部。

重点重新核实文档中提及的校内可信身份注册、默认管理员凭据替换、正式微信配置、iOS/Android 真机、PostgreSQL 并发、多实例与 worker 幂等、备份恢复、脱敏截图、签字验收。它们是待核查线索，不能预设现在仍未完成，也不能因为单元测试通过就判定已解决。

如需百分比，必须提供需求范围、分母、计分规则及对应证据；实现率与验收率分别统计，无法确定项单列。默认优先输出“已实现 X 项、部分 Y 项、未实现 Z 项、待核实 W 项”，并指出上线阻断项，避免虚假精度。

## 七、交付报告格式

输出中文报告，建议保存至 `outputs/` 的带日期文件，避免覆盖历史记录。报告依次包含：

1. **结论**：当前所在阶段，是否具备试点/上线条件，最关键的缺口。
2. **检查基线**：时间、仓库、本地/远程 SHA、工作区状态、访问与测试限制。
3. **项目结构**：目录树、正式主线和关键调用链。
4. **功能矩阵**：逐项实现与验证状态，附证据。
5. **GitHub 状态**：同步关系、PR、Issues、CI、tag/Release，附链接。
6. **验证结果**：本次真实运行的结果、跳过项及未执行原因。
7. **问题清单**：严重度、影响、证据、修复建议、验收方法；区分已确认缺陷与待核实风险。
8. **下一步**：按 P0（试点/上线阻断）、P1（核心体验/可靠性）、P2（优化）排序，注明依赖及需要谁配合。

最后明确回答：“现在能演示什么？现在还不能证明什么？离校内试点还缺什么？离正式上线还缺什么？”

所有结论都必须能追溯到证据。工具无法访问、测试未运行、截图未提供、生产未连接时，直接写“未验证”。完成报告后停止，不自动进入修复或发布。
