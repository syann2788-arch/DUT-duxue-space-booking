import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'


const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const environments = new Set(['development', 'staging', 'production'])


export function validateBuildConfig(environment, apiBaseUrl, appid) {
  if (!environments.has(environment)) throw new Error(`未知构建环境: ${environment}`)
  let parsed
  try {
    parsed = new URL(apiBaseUrl)
  } catch {
    throw new Error('MINIPROGRAM_API_BASE_URL 必须是完整 URL')
  }
  if (!/\/api\/?$/.test(parsed.pathname)) throw new Error('API 地址必须以 /api 结尾')
  if (environment === 'production') {
    const localHosts = new Set(['localhost', '127.0.0.1', '0.0.0.0'])
    if (parsed.protocol !== 'https:') throw new Error('production API 必须使用 HTTPS')
    if (localHosts.has(parsed.hostname) || /^10\.|^192\.168\.|^172\.(1[6-9]|2\d|3[01])\./.test(parsed.hostname)) {
      throw new Error('production API 不能使用本地或局域网地址')
    }
    if (!/^wx[0-9a-f]{16}$/i.test(appid)) throw new Error('production 构建必须提供格式有效的正式 MINIPROGRAM_APP_ID')
  }
}


export function build(environment, env = process.env) {
  const apiBaseUrl = env.MINIPROGRAM_API_BASE_URL || (environment === 'development' ? 'http://127.0.0.1:8000/api' : '')
  const appid = env.MINIPROGRAM_APP_ID || ''
  validateBuildConfig(environment, apiBaseUrl, appid)

  const project = JSON.parse(fs.readFileSync(path.join(root, 'project.config.json'), 'utf8'))
  project.appid = appid
  project.setting = { ...project.setting, urlCheck: environment !== 'development' }

  const output = path.join(root, 'dist', `miniprogram-${environment}`)
  fs.rmSync(output, { recursive: true, force: true })
  fs.mkdirSync(output, { recursive: true })
  fs.cpSync(path.join(root, 'miniprogram'), path.join(output, 'miniprogram'), { recursive: true })

  const version = env.RELEASE_VERSION || 'unreleased'
  const commit = env.GIT_COMMIT || 'unknown'
  const sourceDigest = crypto.createHash('sha256')
    .update(fs.readFileSync(path.join(root, 'miniprogram', 'app.js')))
    .update(fs.readFileSync(path.join(root, 'miniprogram', 'app.json')))
    .digest('hex')
  const generated = `module.exports = ${JSON.stringify({
    environment,
    apiBaseUrl: apiBaseUrl.replace(/\/+$/, ''),
    allowRuntimeOverride: environment === 'development',
    version,
    commit,
  }, null, 2)}\n`
  fs.writeFileSync(path.join(output, 'miniprogram', 'build.config.js'), generated)
  fs.writeFileSync(path.join(output, 'project.config.json'), `${JSON.stringify(project, null, 2)}\n`)
  fs.writeFileSync(path.join(output, 'build-manifest.json'), `${JSON.stringify({
    environment, version, commit, sourceDigest, apiBaseUrl, appid, createdAt: new Date().toISOString(),
  }, null, 2)}\n`)

  const required = ['app.js', 'app.json', 'config.js', 'build.config.js', 'utils/api.js']
  for (const item of required) {
    if (!fs.existsSync(path.join(output, 'miniprogram', item))) throw new Error(`产物缺少 ${item}`)
  }
  return output
}


if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const environment = process.argv[2] || 'development'
  const output = build(environment)
  process.stdout.write(`${output}\n`)
}
