import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import crypto from 'node:crypto'

import { build, validateBuildConfig } from './build-miniprogram.mjs'
import { verifyBuild } from './verify-miniprogram-build.mjs'

const rootAppid = 'wx78c441ce72d765fc'
const formalEnv = {
  MINIPROGRAM_API_BASE_URL: 'https://space-api.example.edu.cn/api',
  MINIPROGRAM_APP_ID: 'wx1234567890abcdef',
  RELEASE_VERSION: 'v0.1.0-rc.1', GIT_COMMIT: 'a'.repeat(40),
}

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'duxue-build-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  const sources = {
    'project.config.json': JSON.stringify({ appid: rootAppid, miniprogramRoot: 'miniprogram/', setting: { urlCheck: false } }),
    'miniprogram/app.js': 'App({})', 'miniprogram/app.json': '{"pages":["pages/home/home"]}',
    'miniprogram/config.js': 'module.exports = {}',
    'miniprogram/build.config.js': 'module.exports = { environment: "development" }',
    'miniprogram/utils/api.js': 'module.exports = {}',
    'miniprogram/pages/home/home.js': 'Page({})',
    'miniprogram/pages/home/home.wxml': '<view>预约</view>',
    'miniprogram/assets/logo.png': Buffer.from([0, 255, 1, 2]),
  }
  for (const [name, bytes] of Object.entries(sources)) {
    fs.mkdirSync(path.dirname(path.join(root, name)), { recursive: true })
    fs.writeFileSync(path.join(root, name), bytes)
  }
  return { root, sources }
}

function manifest(output) { return JSON.parse(fs.readFileSync(path.join(output, 'build-manifest.json'), 'utf8')) }
function generatedConfig(output) {
  return JSON.parse(fs.readFileSync(path.join(output, 'miniprogram/build.config.js'), 'utf8').replace(/^module.exports = /, ''))
}


test('development accepts local HTTP API', () => {
  assert.doesNotThrow(() => validateBuildConfig('development', 'http://127.0.0.1:8000/api', ''))
})

test('production rejects unsafe or incomplete configuration', () => {
  assert.throws(() => validateBuildConfig('production', 'http://api.example.edu.cn/api', 'wx123'), /HTTPS/)
  assert.throws(() => validateBuildConfig('production', 'https://192.168.1.8/api', 'wx1234567890abcdef'), /局域网/)
  assert.throws(() => validateBuildConfig('production', 'https://api.example.edu.cn/api', ''), /APP_ID/)
})

test('production accepts a formal HTTPS configuration', () => {
  assert.doesNotThrow(() => validateBuildConfig('production', 'https://space-api.example.edu.cn/api', 'wx1234567890abcdef'))
})

test('development falls back to root AppID, supports override and preserves every source byte', t => {
  const { root, sources } = fixture(t)
  const output = build('development', {}, { root })
  assert.equal(manifest(output).appid, rootAppid)
  assert.equal(JSON.parse(fs.readFileSync(path.join(output, 'project.config.json'))).appid, rootAppid)
  assert.equal(generatedConfig(output).allowRuntimeOverride, true)
  build('development', { MINIPROGRAM_APP_ID: formalEnv.MINIPROGRAM_APP_ID }, { root })
  assert.equal(manifest(output).appid, formalEnv.MINIPROGRAM_APP_ID)
  for (const [name, bytes] of Object.entries(sources)) {
    assert.deepEqual(fs.readFileSync(path.join(root, name)), Buffer.from(bytes))
  }
})

test('production requires explicit AppID, version and full commit before replacing output', t => {
  const { root } = fixture(t)
  const output = build('production', formalEnv, { root })
  const before = fs.readFileSync(path.join(output, 'build-manifest.json'))
  for (const [key, invalid, pattern] of [
    ['MINIPROGRAM_APP_ID', '', /APP_ID/], ['RELEASE_VERSION', '', /RELEASE_VERSION/],
    ['RELEASE_VERSION', 'unreleased', /RELEASE_VERSION/], ['RELEASE_VERSION', 'unknown', /RELEASE_VERSION/],
    ['GIT_COMMIT', '', /GIT_COMMIT/], ['GIT_COMMIT', 'unknown', /GIT_COMMIT/],
    ['GIT_COMMIT', 'abcdef1', /GIT_COMMIT/], ['GIT_COMMIT', 'z'.repeat(40), /GIT_COMMIT/],
  ]) {
    assert.throws(() => build('production', { ...formalEnv, [key]: invalid }, { root }), pattern)
    assert.deepEqual(fs.readFileSync(path.join(output, 'build-manifest.json')), before)
  }
  assert.equal(generatedConfig(output).allowRuntimeOverride, false)
  assert.equal(manifest(output).version, formalEnv.RELEASE_VERSION)
  assert.equal(manifest(output).commit, formalEnv.GIT_COMMIT)
})

test('inventories cover every source and delivered file, with correct byte lengths and hashes', t => {
  const { root, sources } = fixture(t)
  const output = build('production', formalEnv, { root })
  const data = verifyBuild(output)
  assert.deepEqual(data.sourceFiles.map(file => file.path), Object.keys(sources).sort())
  assert.deepEqual(data.files.map(file => file.path), Object.keys(sources).sort())
  for (const [base, files] of [[root, data.sourceFiles], [output, data.files]]) {
    for (const file of files) {
      const bytes = fs.readFileSync(path.join(base, file.path))
      assert.equal(file.size, bytes.length)
      assert.equal(file.sha256, crypto.createHash('sha256').update(bytes).digest('hex'))
    }
  }
  assert.equal(data.sourceDigest, crypto.createHash('sha256').update(JSON.stringify(data.sourceFiles)).digest('hex'))
  assert.equal(data.artifactDigest, crypto.createHash('sha256').update(JSON.stringify(data.files)).digest('hex'))
})

test('identical builds keep both digests stable despite a different timestamp', async t => {
  const { root } = fixture(t)
  const first = manifest(build('production', formalEnv, { root }))
  await new Promise(resolve => setTimeout(resolve, 10))
  const second = manifest(build('production', formalEnv, { root }))
  assert.notEqual(first.createdAt, second.createdAt)
  assert.equal(first.sourceDigest, second.sourceDigest)
  assert.equal(first.artifactDigest, second.artifactDigest)
  assert.deepEqual(first.files, second.files)
})

test('page, public utility, binary asset, addition, rename and removal change both digests', t => {
  const { root } = fixture(t)
  let previous = manifest(build('production', formalEnv, { root }))
  const mutations = [
    () => fs.appendFileSync(path.join(root, 'miniprogram/pages/home/home.wxml'), '<view>修改</view>'),
    () => fs.appendFileSync(path.join(root, 'miniprogram/utils/api.js'), '\n// changed'),
    () => fs.appendFileSync(path.join(root, 'miniprogram/assets/logo.png'), Buffer.from([9])),
    () => fs.writeFileSync(path.join(root, 'miniprogram/assets/new.txt'), 'new'),
    () => fs.renameSync(path.join(root, 'miniprogram/assets/new.txt'), path.join(root, 'miniprogram/assets/renamed.txt')),
    () => fs.unlinkSync(path.join(root, 'miniprogram/assets/renamed.txt')),
  ]
  for (const mutate of mutations) {
    mutate()
    const current = verifyBuild(build('production', formalEnv, { root }))
    assert.notEqual(current.sourceDigest, previous.sourceDigest)
    assert.notEqual(current.artifactDigest, previous.artifactDigest)
    previous = current
  }
})

test('each deployment parameter changes artifact digest while source digest remains stable', t => {
  const { root } = fixture(t)
  const baseline = manifest(build('production', formalEnv, { root }))
  for (const override of [
    { MINIPROGRAM_API_BASE_URL: 'https://other.example.edu.cn/api' },
    { MINIPROGRAM_APP_ID: rootAppid }, { RELEASE_VERSION: 'v0.1.0-rc.2' }, { GIT_COMMIT: 'b'.repeat(40) },
  ]) {
    const current = verifyBuild(build('production', { ...formalEnv, ...override }, { root }))
    assert.equal(current.sourceDigest, baseline.sourceDigest)
    assert.notEqual(current.artifactDigest, baseline.artifactDigest)
  }
})

test('verification rejects modified, missing and extra delivered files', t => {
  const { root } = fixture(t)
  for (const mutate of [
    output => fs.appendFileSync(path.join(output, 'miniprogram/utils/api.js'), 'tampered'),
    output => fs.unlinkSync(path.join(output, 'miniprogram/assets/logo.png')),
    output => fs.writeFileSync(path.join(output, 'extra.txt'), 'unexpected'),
  ]) {
    const output = build('production', formalEnv, { root })
    mutate(output)
    assert.throws(() => verifyBuild(output), /不一致/)
  }
})
