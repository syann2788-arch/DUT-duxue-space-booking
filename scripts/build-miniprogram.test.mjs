import test from 'node:test'
import assert from 'node:assert/strict'

import { validateBuildConfig } from './build-miniprogram.mjs'


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
