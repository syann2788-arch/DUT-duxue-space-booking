const { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } = require('node:fs')
const { join, resolve } = require('node:path')

const environment = process.argv[2] || 'development'
const allowed = new Set(['development', 'staging', 'production'])
if (!allowed.has(environment)) throw new Error(`未知构建环境: ${environment}`)

const repositoryRoot = resolve(__dirname, '..', '..')
const outputRoot = join(repositoryRoot, 'dist', 'wechat')
const outputMiniprogram = join(outputRoot, 'miniprogram')
const sourceMiniprogram = join(repositoryRoot, 'miniprogram')
const project = JSON.parse(readFileSync(join(repositoryRoot, 'project.config.json'), 'utf8'))
const defaultDevelopmentUrl = 'http://127.0.0.1:8000/api'
const apiBaseUrl = String(process.env.MINIPROGRAM_API_BASE_URL || (environment === 'development' ? defaultDevelopmentUrl : '')).replace(/\/+$/, '')
const appId = String(process.env.MINIPROGRAM_APP_ID || (environment === 'development' ? project.appid : '')).trim()

function sleep(milliseconds) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds)
}

function removeWithRetry(path) {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    try {
      rmSync(path, { recursive: true, force: true, maxRetries: 2, retryDelay: 100 })
    } catch (error) {
      if (attempt === 9) throw error
    }
    if (!existsSync(path)) return
    sleep(200)
  }
  console.warn(`OneDrive 正在占用旧构建目录，将逐文件覆盖: ${path}`)
  return false
}

function copyTree(source, destination) {
  mkdirSync(destination, { recursive: true })
  for (const entry of readdirSync(source)) {
    const sourcePath = join(source, entry)
    if (/[\\/](node_modules|tests|scripts)([\\/]|$)/.test(sourcePath) || /package(-lock)?\.json$/.test(sourcePath)) continue
    const destinationPath = join(destination, entry)
    if (statSync(sourcePath).isDirectory()) copyTree(sourcePath, destinationPath)
    else copyFileSync(sourcePath, destinationPath)
  }
}

if (!apiBaseUrl) throw new Error('必须设置 MINIPROGRAM_API_BASE_URL')
if (environment !== 'development') {
  if (!apiBaseUrl.startsWith('https://')) throw new Error('staging/production API 必须使用 HTTPS')
  if (/localhost|127\.0\.0\.1|example\.(com|edu)/i.test(apiBaseUrl)) throw new Error('拒绝本地或占位 API 地址')
  if (!appId) throw new Error('staging/production 必须设置 MINIPROGRAM_APP_ID')
}

removeWithRetry(outputRoot)
sleep(300)
mkdirSync(outputRoot, { recursive: true })
copyTree(sourceMiniprogram, outputMiniprogram)

const envVersion = environment === 'production' ? 'release' : (environment === 'staging' ? 'trial' : 'develop')
const generated = {
  environment,
  version: process.env.RELEASE_VERSION || '0.2.0-dev',
  commit: process.env.GIT_SHA || 'local',
  apiBaseUrls: { develop: '', trial: '', release: '', [envVersion]: apiBaseUrl }
}
writeFileSync(join(outputMiniprogram, 'config.generated.js'), `module.exports = ${JSON.stringify(generated, null, 2)}\n`)

project.miniprogramRoot = 'miniprogram/'
project.appid = appId
project.cloud = false
project.setting = Object.assign({}, project.setting, { urlCheck: environment !== 'development' })
writeFileSync(join(outputRoot, 'project.config.json'), `${JSON.stringify(project, null, 2)}\n`)
writeFileSync(join(outputRoot, 'BUILD_INFO.json'), `${JSON.stringify(generated, null, 2)}\n`)
console.log(`Built ${environment} WeChat artifact at ${outputRoot}`)
