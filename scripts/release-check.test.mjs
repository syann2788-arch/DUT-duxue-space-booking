import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { checkRelease, validateAcceptance, acceptanceChecks, acceptanceRoles } from './release-check.mjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

test('release baseline contains an explicit version and no false production claim', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))
  const roadmap = fs.readFileSync(path.join(root, 'ROADMAP.md'), 'utf8')
  const baseline = fs.readFileSync(path.join(root, 'docs/PILOT_RELEASE_BASELINE.md'), 'utf8')
  assert.match(pkg.version, /^0\.\d+\.\d+-rc\.\d+$/)
  assert.match(roadmap, /待部署验收/)
  assert.match(roadmap, /学校正式验收尚未完成/)
  assert.match(baseline, /不得创建 Release/)
  const workflow = fs.readFileSync(path.join(root, '.github/workflows/quality.yml'), 'utf8')
  assert.match(workflow, /tags: \["v\*"\]/)
  assert.match(workflow, /Require approved production configuration/)
})

test('community entry points exist and protect sensitive reports', () => {
  for (const file of ['CONTRIBUTING.md', 'SUPPORT.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md']) {
    assert.equal(fs.existsSync(path.join(root, file)), true, file)
  }
  const config = fs.readFileSync(path.join(root, '.github/ISSUE_TEMPLATE/config.yml'), 'utf8')
  assert.match(config, /blank_issues_enabled: false/)
  assert.match(config, /security/)
})

test('demo and metrics artifacts prohibit real personal data', () => {
  const demo = fs.readFileSync(path.join(root, 'docs/DEMO.md'), 'utf8')
  const metrics = fs.readFileSync(path.join(root, 'docs/PILOT_METRICS.md'), 'utf8')
  assert.match(demo, /只允许在本地开发环境/)
  assert.match(demo, /不得使用真实/)
  assert.match(metrics, /不得记录/)
})

test('local completion and direct dependency license inventory are auditable', () => {
  const inventory = fs.readFileSync(path.join(root, 'docs/DEPENDENCY_LICENSE_INVENTORY.md'), 'utf8')
  const report = fs.readFileSync(path.join(root, 'docs/LOCAL_COMPLETION_REPORT.md'), 'utf8')
  const workflow = fs.readFileSync(path.join(root, '.github/workflows/quality.yml'), 'utf8')
  const requirements = fs.readFileSync(path.join(root, 'backend/requirements.txt'), 'utf8')
  const jwtRequirement = requirements.match(/^PyJWT==([^\s]+)$/m)
  assert.ok(jwtRequirement, 'PyJWT must have a pinned version')
  assert.ok(inventory.includes(`| PyJWT | ${jwtRequirement[1]} | MIT |`), 'license inventory must match the pinned PyJWT version')
  assert.match(inventory, /项目自身采用何种许可证/)
  assert.match(report, /未发现已知漏洞/)
  assert.doesNotMatch(workflow, /dependency-audit:[\s\S]*?continue-on-error: true/)
})

// Human acceptance is intentionally separate from the local source candidate.
// These exercise refusal paths rather than merely matching policy prose.

test('source candidate needs no school credentials or formal screenshots', () => {
  const result = checkRelease({ root, mode: 'candidate' })
  assert.deepEqual(result.errors, [])
  assert.match(result.version, /-rc\.\d+$/)
})

test('ambiguous tag and unaccepted production release are refused', () => {
  assert.ok(checkRelease({ root, tagMode: true }).errors.some(error => error.includes('--tag必须明确')))
  const errors = checkRelease({ root, mode: 'production' }).errors
  assert.ok(errors.some(error => error.includes('稳定版本')))
  assert.ok(errors.some(error => error.includes('--evidence')))
})

test('formal acceptance requires every check, five signatures, and matching commit', () => {
  const sha = 'a'.repeat(40)
  const record = { schemaVersion: 1, version: '0.1.0', sourceCommit: sha,
    checks: Object.fromEntries(acceptanceChecks.map(id => [id, { passed: true, evidence: 'controlled-record:test' }])),
    signoffs: Object.fromEntries(acceptanceRoles.map(role => [role, { name: 'Synthetic Reviewer', date: '2026-10-02', decision: 'approved', evidence: 'controlled-signature:test' }])) }
  assert.deepEqual(validateAcceptance(record, '0.1.0', sha), [])
  for (const id of acceptanceChecks) {
    const incomplete = structuredClone(record)
    incomplete.checks[id].passed = false
    assert.ok(validateAcceptance(incomplete, '0.1.0', sha).some(error => error.includes(id)))
  }
  for (const role of acceptanceRoles) {
    const incomplete = structuredClone(record)
    incomplete.signoffs[role].decision = 'pending'
    assert.ok(validateAcceptance(incomplete, '0.1.0', sha).some(error => error.includes(role)))
  }
  assert.ok(validateAcceptance(record, '0.1.0', 'b'.repeat(40)).length)
  const template = JSON.parse(fs.readFileSync(path.join(root, 'docs/RELEASE_ACCEPTANCE.example.json'), 'utf8'))
  assert.ok(validateAcceptance(template, '0.1.0', sha).length)
})
