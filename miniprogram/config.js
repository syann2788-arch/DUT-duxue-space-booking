const buildConfig = require('./build.config')
const DEFAULT_API_BASE_URL = buildConfig.apiBaseUrl

function normalizeBaseUrl(value) {
  return String(value || '').trim().replace(/\/+$/, '')
}

function getApiBaseUrl() {
  if (!buildConfig.allowRuntimeOverride) return DEFAULT_API_BASE_URL
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
  BUILD_ENV: buildConfig.environment,
  BUILD_VERSION: buildConfig.version,
  BUILD_COMMIT: buildConfig.commit,
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
