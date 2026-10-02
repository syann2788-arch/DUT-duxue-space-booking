import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const defaultRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export const acceptanceChecks = ['ci', 'p0Disposition', 'productionConfiguration', 'identityAndPrivacy', 'databaseAndRecovery', 'realDevicesAndMessages', 'rightsAndLicenses']
export const acceptanceRoles = ['maintainer', 'business', 'operations', 'wechat', 'privacy']

// This validates the supplied record's completeness, not the authenticity of a
// signature or an external CI result. The release owner must verify originals.
export function validateAcceptance(record, version, sourceCommit) {
  const errors = []
  if (!/^[0-9a-f]{40}(?:[0-9a-f]{24})?$/.test(sourceCommit || '')) errors.push('目标提交必须是完整SHA')
  if (record?.schemaVersion !== 1) errors.push('验收记录schemaVersion必须为1')
  if (record?.version !== version || record?.sourceCommit !== sourceCommit) errors.push('验收记录版本/提交与目标不一致')
  for (const id of acceptanceChecks) {
    const check = record?.checks?.[id]
    if (check?.passed !== true || typeof check.evidence !== 'string' || !check.evidence.trim()) errors.push(`验收项缺少通过结论或证据: ${id}`)
  }
  for (const role of acceptanceRoles) {
    const signoff = record?.signoffs?.[role]
    if (signoff?.decision !== 'approved' || typeof signoff.name !== 'string' || !signoff.name.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(signoff.date || '') || typeof signoff.evidence !== 'string' || !signoff.evidence.trim()) errors.push(`缺少签字及证据: ${role}`)
  }
  return errors
}

export function checkRelease({ root = defaultRoot, mode = 'baseline', tagMode = false, evidenceFile = null } = {}) {
  const errors = []
  const read = relative => {
    try { return fs.readFileSync(path.join(root, relative), 'utf8') }
    catch { errors.push(`缺少 ${relative}`); return '' }
  }
  const required = ['CHANGELOG.md', 'ROADMAP.md', 'SECURITY.md', 'CONTRIBUTING.md', 'SUPPORT.md', 'CODE_OF_CONDUCT.md', 'docs/PILOT_RELEASE_BASELINE.md', 'docs/RELEASE_CHECKLIST.md', 'docs/DEMO.md', 'docs/PILOT_METRICS.md', 'docs/GITHUB_ADMIN_SETUP.md', 'docs/DEPENDENCY_LICENSE_INVENTORY.md', 'docs/LOCAL_COMPLETION_REPORT.md', 'docs/HANDOVER_GUIDE.md', 'docs/RELEASE_ACCEPTANCE.example.json', '.github/CODEOWNERS', '.github/pull_request_template.md', '.github/ISSUE_TEMPLATE/bug_report.yml', '.github/ISSUE_TEMPLATE/feature_request.yml', '.github/ISSUE_TEMPLATE/pilot_acceptance.yml']
  for (const relative of required) read(relative)
  let version
  try { version = JSON.parse(read('package.json')).version } catch { errors.push('package.json无效') }
  if (!/^\d+\.\d+\.\d+(?:-rc\.\d+)?$/.test(version || '')) errors.push('package.json缺少有效发布版本')
  if (mode === 'candidate' && !/^\d+\.\d+\.\d+-rc\.\d+$/.test(version || '')) errors.push('源码候选必须使用-rc.N版本')
  if (mode === 'production' && !/^\d+\.\d+\.\d+$/.test(version || '')) errors.push('正式发布必须使用稳定版本，不能使用rc')
  if (tagMode && mode === 'baseline') errors.push('--tag必须明确搭配--candidate或--production')
  const changelog = read('CHANGELOG.md')
  if (!changelog.includes(`## [${version}]`)) errors.push(`CHANGELOG.md缺少${version}章节`)
  for (const heading of ['### 新增', '### 修复', '### 已知限制', '### 迁移与部署', '### 回滚']) if (!changelog.includes(heading)) errors.push(`CHANGELOG.md缺少${heading}`)
  if (!read('README.md').includes(`\`${version}\``)) errors.push('README.md候选版本不一致')
  const workflow = read('.github/workflows/quality.yml')
  if (!workflow.includes('tags: ["v*"]') || !workflow.includes('Require approved production configuration')) errors.push('CI缺少标签触发或正式配置门禁')
  const baseline = read('docs/PILOT_RELEASE_BASELINE.md')
  if (!baseline.includes('v0.1.0 校内试点') || !baseline.includes('负责人角色')) errors.push('发布基线缺少里程碑/责任角色')
  const checklist = read('docs/RELEASE_CHECKLIST.md')
  if (!checklist.includes('不得创建 Release') || !checklist.includes('待部署验收')) errors.push('发布清单缺少阶段区分或禁止发布门槛')

  const git = args => execFileSync('git', args, { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim()
  let commit = null
  if (tagMode || mode === 'production') {
    try {
      commit = git(['rev-parse', '--verify', 'HEAD'])
      if (git(['status', '--porcelain'])) errors.push('发布前工作区必须干净')
      git(['merge-base', '--is-ancestor', commit, 'origin/main'])
    } catch { errors.push('必须在Git仓库刷新origin/main并确认目标提交已合入main') }
  }
  if (tagMode) {
    try {
      const tags = git(['tag', '--list', `v${version}`])
      if (tags) errors.push(`标签v${version}已存在，不得移动或复用`)
    } catch { errors.push('无法核对已有标签') }
  }
  if (mode === 'production') {
    for (const relative of ['docs/assets/screenshots/student-space-guide.png', 'docs/assets/screenshots/student-my-reservations.png', 'docs/assets/screenshots/admin-review.png']) if (!fs.existsSync(path.join(root, relative))) errors.push(`缺少真实脱敏截图: ${relative}`)
    if (!evidenceFile) errors.push('正式发布必须提供--evidence学校验收记录，模板不能作为完成证据')
    else {
      try { errors.push(...validateAcceptance(JSON.parse(fs.readFileSync(evidenceFile, 'utf8')), version, commit)) }
      catch { errors.push('无法读取有效验收JSON') }
    }
  }
  return { errors, version, commit, mode, tagMode }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2)
  const allowed = new Set(['--candidate', '--production', '--tag', '--evidence'])
  let argumentError = null
  for (let i = 0; i < args.length; i++) {
    if (!allowed.has(args[i])) argumentError = `未知参数: ${args[i]}`
    if (args[i] === '--evidence') { if (!args[++i]) argumentError = '--evidence缺少文件路径' }
  }
  if (args.includes('--candidate') && args.includes('--production')) argumentError = '候选与正式模式不能同时使用'
  const result = checkRelease({ mode: args.includes('--production') ? 'production' : args.includes('--candidate') ? 'candidate' : 'baseline', tagMode: args.includes('--tag'), evidenceFile: args.includes('--evidence') ? args[args.indexOf('--evidence') + 1] : null })
  if (argumentError) result.errors.push(argumentError)
  if (result.errors.length) {
    process.stderr.write(result.errors.map(message => `发布检查失败：${message}`).join('\n') + '\n')
    process.exitCode = 1
  } else process.stdout.write(`发布文档/记录检查通过：v${result.version}（${result.mode}）；仍须人工核对CI、权利、审批和原始验收证据。\n`)
}
