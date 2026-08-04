const { getApiBaseUrl } = require('../config')

function buildUrl(path) {
  if (/^https?:\/\//i.test(path)) return path
  return `${getApiBaseUrl()}/${String(path || '').replace(/^\/+/, '')}`
}

function getToken() {
  const app = getApp()
  return (app.globalData && app.globalData.token) || wx.getStorageSync('token') || ''
}

function clearLogin() {
  const app = getApp()
  if (app && typeof app.clearLogin === 'function') {
    app.clearLogin()
    return
  }
  if (app.globalData) {
    app.globalData.token = ''
    app.globalData.user = null
  }
  wx.removeStorageSync('token')
  wx.removeStorageSync('user')
}

function extractError(data, fallback = '请求失败') {
  if (!data) return fallback
  if (typeof data === 'string') return data

  const detail = data.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail)) {
    const messages = detail.map(item => {
      const message = item && (item.msg || item.message)
      return typeof message === 'string' ? message.replace(/^Value error,\s*/i, '') : ''
    }).filter(Boolean)
    if (messages.length) return messages.join('；')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  return data.message || data.msg || data.errMsg || fallback
}

function createError(data, statusCode, fallback) {
  const error = new Error(extractError(data, fallback))
  error.statusCode = statusCode
  error.data = data
  return error
}

function authHeaders(header = {}, token = getToken()) {
  const headers = Object.assign({}, header)
  if (token && !headers.Authorization && !headers.authorization) {
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

function request(path, options = {}) {
  if (path && typeof path === 'object') {
    options = path
    path = options.url
  }

  const tokenAtStart = getToken()
  return new Promise((resolve, reject) => {
    wx.request({
      url: buildUrl(path),
      method: options.method || 'GET',
      data: options.data,
      header: authHeaders(Object.assign({ 'content-type': 'application/json' }, options.header), tokenAtStart),
      timeout: options.timeout || 15000,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
          return
        }
        // A stale unauthenticated request must not erase a token produced by a
        // concurrent wx.login/password login attempt.
        if (res.statusCode === 401 && tokenAtStart && getToken() === tokenAtStart) clearLogin()
        reject(createError(res.data, res.statusCode, `请求失败（${res.statusCode}）`))
      },
      fail(err) {
        reject(createError(err, 0, '网络请求失败，请检查后端服务'))
      }
    })
  })
}

function uploadFile(path, filePath, options = {}) {
  if (path && typeof path === 'object') {
    options = path
    path = options.url
    filePath = options.filePath
  }

  const tokenAtStart = getToken()
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: buildUrl(path),
      filePath,
      name: options.name || 'file',
      formData: options.formData || {},
      header: authHeaders(options.header, tokenAtStart),
      timeout: options.timeout || 30000,
      success(res) {
        let data = res.data
        if (typeof data === 'string') {
          try {
            data = JSON.parse(data)
          } catch (error) {
            // Keep a non-JSON server response so the caller can inspect it.
          }
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(data)
          return
        }
        if (res.statusCode === 401 && tokenAtStart && getToken() === tokenAtStart) clearLogin()
        reject(createError(data, res.statusCode, `上传失败（${res.statusCode}）`))
      },
      fail(err) {
        reject(createError(err, 0, '上传失败，请检查网络连接'))
      }
    })
  })
}

module.exports = {
  request,
  uploadFile,
  extractError
}
