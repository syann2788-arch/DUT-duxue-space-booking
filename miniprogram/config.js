const generated = require('./config.generated')

const API_BASE_URLS = Object.assign({
  develop: 'http://127.0.0.1:8000/api',
  trial: '',
  release: ''
}, generated.apiBaseUrls || {})

function normalizeBaseUrl(value) {
  return String(value || '').trim().replace(/\/+$/, '')
}

function getEnvVersion() {
  try {
    return wx.getAccountInfoSync().miniProgram.envVersion || 'develop'
  } catch (error) {
    return 'develop'
  }
}

function getApiBaseUrl() {
  const envVersion = getEnvVersion()
  const developmentOverride = envVersion === 'develop' ? normalizeBaseUrl(wx.getStorageSync('apiBaseUrl')) : ''
  const value = developmentOverride || normalizeBaseUrl(API_BASE_URLS[envVersion])
  if (!value) throw new Error(`未配置 ${envVersion} 环境 API 地址`)
  if (envVersion !== 'develop' && !value.startsWith('https://')) {
    throw new Error(`${envVersion} 环境 API 必须使用 HTTPS`)
  }
  return value
}

function getServerUrl() {
  return getApiBaseUrl().replace(/\/api$/i, '')
}

function toServerUrl(path) {
  if (!path || /^https?:\/\//i.test(path)) return path || ''
  return `${getServerUrl()}/${String(path).replace(/^\/+/, '')}`
}

const config = {
  DEFAULT_API_BASE_URL: API_BASE_URLS.develop,
  API_BASE_URLS,
  getApiBaseUrl,
  getServerUrl,
  toServerUrl
}

Object.defineProperties(config, {
  API_BASE_URL: { enumerable: true, get: getApiBaseUrl },
  SERVER_URL: { enumerable: true, get: getServerUrl }
})

module.exports = config
