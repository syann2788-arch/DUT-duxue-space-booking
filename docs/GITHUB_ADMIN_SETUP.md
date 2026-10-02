# GitHub 仓库管理员配置清单

以下设置不能通过普通代码提交生效，必须由仓库所有者在 GitHub 网页或受控管理工具中完成。完成后把脱敏截图或设置链接记录到试点验收 Issue。

## 仓库首页

- Description：`大连理工大学笃学书院原生微信小程序 + FastAPI 空间预约校内试点项目`
- Website：在有正式脱敏演示页之前留空，不要填写本地地址或临时隧道。
- Topics：`wechat-miniprogram`、`fastapi`、`postgresql`、`space-booking`、`campus`、`china`
- 暂不启用 Discussions；支持入口统一走结构化 Issue 和 `SUPPORT.md`。

## Milestone

创建 `v0.1.0 校内试点`，目标日期由学校首次试点会议确定。把 `ROADMAP.md` 和 `docs/PILOT_RELEASE_BASELINE.md` 列出的阻断 Issue 纳入，并为每个 Issue 指定具体负责人、优先级和状态；学校/微信依赖增加 `external-blocker` 标签。

建议标签：

- 优先级：`P0`、`P1`、`P2`；
- 状态：`needs-triage`、`blocked`、`ready`、`acceptance`；
- 依赖：`external-blocker`；
- 领域：`security`、`backend`、`miniprogram`、`ops`、`documentation`。

## `main` 分支规则

- 必须通过 Pull Request；
- 至少 1 名批准者；
- 新提交后取消过期批准；
- 要求全部对话已解决；
- 必需检查：`Backend tests`、`Miniprogram build policy`、`PostgreSQL concurrency`；
- 禁止 force-push 和删除 `main`；
- 管理员也不得绕过以上规则。

当前依赖审计仍是观察基线，只有在确定漏洞处置流程后再设为必需检查，避免无责任人的外部漏洞报告永久阻塞全部 PR。

## 安全入口

在 **Settings → Security → Private vulnerability reporting** 启用私下漏洞报告。确认 `SECURITY.md` 的入口可用后，再对外邀请安全报告；不要把个人邮箱或未获授权的学校联系方式写进公开仓库。

## 第一个候选 Release

1. 确认 `main` 指向已签字验收的提交并且 Actions 全绿。
2. 在 Actions repository variables 配置 `MINIPROGRAM_API_BASE_URL` 和 `MINIPROGRAM_APP_ID`；标签流水线缺少任一值都会失败。
3. 在干净工作区执行 `npm run release:check -- --tag`。
4. 创建带注释、不可移动的 `v0.1.0-rc.1` 标签并推送；标签会触发 production 构建。
5. 下载并核对 production 小程序构建产物与 `build-manifest.json`。
6. GitHub Release 正文使用 CHANGELOG 对应章节，并链接迁移、回滚、已知限制和验收记录。
7. 标记为 pre-release；完成全部 P0 后才发布 `v0.1.0`。

## 未在本次代码修改中完成的设置

仓库元数据、Milestone、Issue assignee、标签、分支规则、私下漏洞报告和 GitHub Release 都属于远程状态。只有管理员实际配置并留下证据后才算完成，不能仅凭本文件勾选关闭相关 Issue。
