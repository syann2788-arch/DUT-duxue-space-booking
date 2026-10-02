const test = require('node:test')
const assert = require('node:assert/strict')

const pendingRequests = []
let storage = {}
let clearCount = 0
const application = {
  globalData: { token: '', user: null },
  clearLogin() {
    clearCount += 1
    this.globalData.token = ''
    this.globalData.user = null
    delete storage.token
  }
}

global.getApp = () => application
global.wx = {
  getStorageSync: key => storage[key] || '',
  removeStorageSync: key => { delete storage[key] },
  request: options => pendingRequests.push(options)
}

const api = require('../miniprogram/utils/api')

function reset(token = '') {
  pendingRequests.length = 0
  storage = token ? { token } : {}
  clearCount = 0
  application.globalData = { token, user: token ? { id: 1 } : null }
}

test('adds the bearer token and resolves successful requests', async () => {
  reset('token-a')
  const promise = api.request('/auth/me')
  assert.equal(pendingRequests[0].header.Authorization, 'Bearer token-a')
  pendingRequests[0].success({ statusCode: 200, data: { id: 1 } })
  assert.deepEqual(await promise, { id: 1 })
})

test('concurrent 401 responses clear the matching login only once', async () => {
  reset('expired-token')
  const first = api.request('/one').catch(error => error)
  const second = api.request('/two').catch(error => error)
  pendingRequests[0].success({ statusCode: 401, data: { detail: 'expired' } })
  pendingRequests[1].success({ statusCode: 401, data: { detail: 'expired' } })
  const errors = await Promise.all([first, second])
  assert.deepEqual(errors.map(error => error.statusCode), [401, 401])
  assert.equal(clearCount, 1)
  assert.equal(application.globalData.token, '')
})

test('a stale 401 cannot erase a newer interactive login', async () => {
  reset('old-token')
  const promise = api.request('/slow').catch(error => error)
  application.globalData.token = 'new-token'
  storage.token = 'new-token'
  pendingRequests[0].success({ statusCode: 401, data: { detail: 'old request expired' } })
  assert.equal((await promise).statusCode, 401)
  assert.equal(clearCount, 0)
  assert.equal(application.globalData.token, 'new-token')
})

test('normalizes validation error messages for the UI', () => {
  assert.equal(api.extractError({ detail: [{ msg: 'Value error, 学号格式错误' }] }), '学号格式错误')
})
