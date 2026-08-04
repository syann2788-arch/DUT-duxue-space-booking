const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000/api'

function normalizeBaseUrl(value) {
  return String(value || '').trim().replace(/\/+$/, '')
}

function getApiBaseUrl() {
  return normalizeBaseUrl(wx.getStorageSync('apiBaseUrl')) || DEFAULT_API_BASE_URL
}

function getServerUrl() {
  return getApiBaseUrl().replace(/\/api$/i, '')
}

function toServerUrl(path) {
  if (!path || /^https?:\/\//i.test(path)) return path || ''
  return `${getServerUrl()}/${String(path).replace(/^\/+/, '')}`
}

const config = {
  DEFAULT_API_BASE_URL,
  getApiBaseUrl,
  getServerUrl,
  toServerUrl
}

Object.defineProperties(config, {
  API_BASE_URL: { enumerable: true, get: getApiBaseUrl },
  SERVER_URL: { enumerable: true, get: getServerUrl }
})

module.exports = config
