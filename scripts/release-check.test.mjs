import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

test('release baseline contains an explicit version and no false production claim', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'))
  const roadmap = fs.readFileSync(path.join(root, 'ROADMAP.md'), 'utf8')
  const baseline = fs.readFileSync(path.join(root, 'docs/PILOT_RELEASE_BASELINE.md'), 'utf8')
  assert.match(pkg.version, /^0\.\d+\.\d+-rc\.\d+$/)
  assert.match(roadmap, /尚未发布/)
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
