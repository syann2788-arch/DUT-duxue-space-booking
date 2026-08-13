import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const tagMode = process.argv.includes('--tag')

function fail(message) {
  process.stderr.write(`发布检查失败：${message}\n`)
  process.exitCode = 1
}

function read(relative) {
  return fs.readFileSync(path.join(root, relative), 'utf8')
}

const required = [
  'CHANGELOG.md', 'ROADMAP.md', 'SECURITY.md', 'CONTRIBUTING.md', 'SUPPORT.md',
  'CODE_OF_CONDUCT.md', 'docs/PILOT_RELEASE_BASELINE.md', 'docs/RELEASE_CHECKLIST.md',
  'docs/DEMO.md', 'docs/PILOT_METRICS.md', 'docs/GITHUB_ADMIN_SETUP.md', '.github/pull_request_template.md',
  '.github/ISSUE_TEMPLATE/bug_report.yml', '.github/ISSUE_TEMPLATE/feature_request.yml',
  '.github/ISSUE_TEMPLATE/pilot_acceptance.yml'
]
required.push('.github/CODEOWNERS')

for (const relative of required) {
  if (!fs.existsSync(path.join(root, relative))) fail(`缺少 ${relative}`)
}

const packageJson = JSON.parse(read('package.json'))
const version = packageJson.version
if (!/^0\.\d+\.\d+(?:-rc\.\d+)?$/.test(version || '')) fail('package.json 缺少候选版语义版本')

const changelog = read('CHANGELOG.md')
if (!changelog.includes(`## [${version}]`)) fail(`CHANGELOG.md 缺少 ${version} 章节`)
for (const heading of ['### 新增', '### 修复', '### 已知限制', '### 迁移与部署', '### 回滚']) {
  if (!changelog.includes(heading)) fail(`CHANGELOG.md 缺少 ${heading}`)
}

const readme = read('README.md')
if (!readme.includes(`\`${version}\``)) fail(`README.md 未声明当前候选版本 ${version}`)

const workflow = read('.github/workflows/quality.yml')
if (!workflow.includes('tags: ["v*"]')) fail('CI 未监听版本标签')
if (!workflow.includes('Require approved production configuration')) fail('标签构建未强制校验正式配置')

const baseline = read('docs/PILOT_RELEASE_BASELINE.md')
if (!baseline.includes('v0.1.0 校内试点')) fail('发布基线缺少目标里程碑')
if (!baseline.includes('负责人角色')) fail('发布基线缺少负责人角色')

const releaseChecklist = read('docs/RELEASE_CHECKLIST.md')
if (!releaseChecklist.includes('不得创建 Release')) fail('发布清单必须明确未通过时禁止发布')

const gitAvailable = fs.existsSync(path.join(root, '.git'))
if (tagMode && gitAvailable) {
  const screenshots = [
    'docs/assets/screenshots/student-space-guide.png',
    'docs/assets/screenshots/student-my-reservations.png',
    'docs/assets/screenshots/admin-review.png'
  ]
  for (const screenshot of screenshots) {
    if (!fs.existsSync(path.join(root, screenshot))) fail(`标签前缺少脱敏正式客户端截图 ${screenshot}`)
  }
  let dirty = ''
  try {
    dirty = execFileSync('git', ['status', '--porcelain'], { cwd: root, encoding: 'utf8' }).trim()
  } catch (error) {
    fail(`无法检查 Git 状态：${error.message}`)
  }
  if (dirty) fail('创建标签前工作区必须干净')
  const expectedTag = `v${version}`
  try {
    execFileSync('git', ['rev-parse', '-q', '--verify', `refs/tags/${expectedTag}`], { cwd: root, stdio: 'ignore' })
    fail(`标签 ${expectedTag} 已存在；版本标签不可移动或覆盖`)
  } catch (error) {
    if (error.status === undefined) fail(`无法检查标签：${error.message}`)
  }
}

if (!process.exitCode) process.stdout.write(`发布文档基线通过：v${version}${tagMode ? '（标签前检查）' : ''}\n`)
