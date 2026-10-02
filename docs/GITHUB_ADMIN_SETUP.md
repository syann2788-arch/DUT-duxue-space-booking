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

## 源码候选pre-release（待部署验收）

1. 维护者确认本次候选交付/公开范围，核对固定main提交、四项核心CI及Handover package，确认权利与敏感数据风险。
2. 按 [交付指南](HANDOVER_GUIDE.md)准备两份ZIP、教程/模板、完整清单和SHA256SUMS；学校微信配置不齐时明确省略微信构建包。
3. 干净工作区、刷新origin/main后执行`npm run release:check -- --candidate --tag`，另行核对真实CI/评审记录。
4. 创建新带注释`v0.1.0-rc.N`标签并推送，标签CI生成源码材料；rc不强制production配置，不代表学校微信联调已通过。
5. 标签CI成功后从该标签重新打包并校验；manifest的版本/提交/标签一致。Release正文写明“待部署验收”、已知限制、部署/回滚和学校待办。
6. 创建GitHub Release时标记pre-release，不标正式latest；本轮只准备本地工具/材料，没有执行远程Release。

## 学校正式上线Release

保留发布清单B节全部生产验证与五角色签字。冻结稳定版本，在受控渠道填验收记录，执行`release:check --production --tag --evidence /受控路径/acceptance.json`并人工核验原件。稳定标签强制配置repository variables `MINIPROGRAM_API_BASE_URL`、`MINIPROGRAM_APP_ID`，production构建/校验仍必须通过。AppSecret只注入学校后端，不能放入这些变量或小程序包。脚本不自动创建Release或选择许可证。

## 未在本次代码修改中完成的设置

仓库元数据、Milestone、Issue assignee、标签、分支规则、私下漏洞报告和 GitHub Release 都属于远程状态。只有管理员实际配置并留下证据后才算完成，不能仅凭本文件勾选关闭相关 Issue。
