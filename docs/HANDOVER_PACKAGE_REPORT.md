# 第13–14项实施与验证记录

日期：2026-10-03（本轮跨午夜执行）。本轮基线：PR #30实际合入main的ee3b0a72fd1e2ca52d464209ee2060f2f83185b5；main运行 [37027900993](https://github.com/syann2788-arch/DUT-duxue-space-booking/actions/runs/37027900993)四项核心CI成功。本轮新增工具/文档的实际提交与包摘要以handover-manifest.json为准，避免在提交自己的报告里填写无法自引用的HEAD。

## 完成范围

- 第13项：RELEASE_CHECKLIST、PILOT_RELEASE_BASELINE、README、ROADMAP、CHANGELOG和GitHub管理员教程区分候选源码pre-release与正式上线。源码可先交接为待部署验收，公开候选仍须维护者确认、main/CI、权利与包核对；正式保留全部学校配置、真机、生产恢复、隐私与五角色签字。
- release-check支持candidate、production与明确的tag检查；正式版拒绝rc/空验收记录/缺少检查证据或签字/提交错配。模板为未通过、待签字，不把模板当作验收；脚本只检查完整性，原件真实性由发布负责人核对。
- rc标签CI不再误要求生产地址和AppID，稳定标签仍强制production配置。新增Handover package作业，测试导出/校验并在rc阶段上传源码材料，PR产物标记draft。
- 第14项：HANDOVER_GUIDE、接收登记模板、固定Git树导出与独立校验工具；源码ZIP、交付合集、完整文件/档案摘要、可选微信构建均对应同一提交。模板与秘密分开，包不含本地运行数据，已有输出拒绝覆盖。
- 可选微信构建只从该提交的临时源码生成，自动注入版本/提交、校验构建与源码清单；时间戳取提交时间，同输入ZIP摘要可重复。独立校验不执行被检ZIP中的代码。

## 本轮实际本地测试

- `npm test`：33通过（构建10、小程序16、发布策略7）。
- `python3 scripts/test_handover_package.py`：10通过，使用临时Git仓库和ZIP。覆盖同输入重复字节、脏工作区、未合入main、draft状态、已提交敏感路径、符号链接、标签错配、缺失/修改/新增文件、ZIP重复/越界路径、替换内嵌源码及可选微信构建。可选构建使用synthetic.example.invalid，仅为测试夹具，不是学校配置。
- 文档链接与Python/Node语法检查通过；具体最新链接数量以命令输出为准。
- 后端业务源码未改动，本轮不把第12项的54/2与PG2数字写成新本地测试；新PR完整远程结果保存于对应PR说明。

## 包与解压验证的复现

代码与教程提交后，执行`python3 scripts/package_handover.py pack --ref HEAD --draft`；输出目录按版本/提交命名，内容为source.zip、handover.zip、handover-manifest.json、SHA256SUMS。实际输出文件/长度/摘要直接查看manifest并用verify命令独立核对。本地预检尚未对应远程不可变版本标签，tag为null；不能当作已批准的Release附件。

将source.zip解压到临时目录，使用其自带校验脚本核对原包，运行文档链接检查、npm测试和开发构建/构建校验；确认来自该包的源码可以重建。重复同一提交到第二个临时输出目录，比较全部文件摘要。没有读取或修改已有.env、数据库、真实照片和人员名单。

## 仍由学校/维护者执行

- 本轮PR审核/合入main、核对新main CI，维护者确认公开候选预发布与权利；创建不可变标签、按标签重新打包、实际GitHub pre-release和接收登记。
- 真实AppID权限、学校HTTPS、AppSecret/模板、微信体验/审核发布；本轮不附占位学校构建包。
- 学校独立部署、生产快照/媒体恢复、iPhone/Android、可信身份/业务歧义、维护期限与正式签字。

第13–14项完成的是本地规则、工具、教程和候选预检验证；没有把候选准备写成学校正式交付或生产上线。
