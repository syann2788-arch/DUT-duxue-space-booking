import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'

const defaultRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const environments = new Set(['development', 'staging', 'production'])

export function validateBuildConfig(environment, apiBaseUrl, appid) {
  if (!environments.has(environment)) throw new Error(`未知构建环境: ${environment}`)
  let parsed
  try { parsed = new URL(apiBaseUrl) } catch {
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

export function validateReleaseMetadata(environment, version, commit) {
  if (environment !== 'production') return
  if (!/^v?\d+\.\d+\.\d+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?(?:\+[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$/.test(version)) {
    throw new Error('production 构建必须提供版本号 RELEASE_VERSION，例如 v0.1.0-rc.1')
  }
  if (!/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/i.test(commit)) {
    throw new Error('production 构建必须提供完整提交编号 GIT_COMMIT，不能使用 unknown 或短编号')
  }
}

function sha256(bytes) { return crypto.createHash('sha256').update(bytes).digest('hex') }
function comparePaths(left, right) { return left.path < right.path ? -1 : left.path > right.path ? 1 : 0 }

// Paths, lengths and hashes are framed as JSON, so filename/content boundaries
// are unambiguous. File order and timestamps do not affect the aggregate hash.
export function fileInventory(directory, exclude = new Set()) {
  const files = []
  function walk(relative) {
    for (const entry of fs.readdirSync(path.join(directory, relative), { withFileTypes: true })) {
      const name = relative ? `${relative}/${entry.name}` : entry.name
      if (exclude.has(name)) continue
      if (entry.isSymbolicLink()) throw new Error(`构建文件不能是符号链接: ${name}`)
      if (entry.isDirectory()) walk(name)
      else if (entry.isFile()) {
        const bytes = fs.readFileSync(path.join(directory, name))
        files.push({ path: name, size: bytes.length, sha256: sha256(bytes) })
      } else throw new Error(`不支持的构建文件类型: ${name}`)
    }
  }
  walk('')
  return files.sort(comparePaths)
}

export function inventoryDigest(files) {
  return sha256(JSON.stringify([...files].sort(comparePaths)))
}

export function build(environment, env = process.env, options = {}) {
  const root = options.root || defaultRoot
  const projectPath = path.join(root, 'project.config.json')
  const projectBytes = fs.readFileSync(projectPath)
  const project = JSON.parse(projectBytes.toString('utf8'))
  const apiBaseUrl = (env.MINIPROGRAM_API_BASE_URL || (environment === 'development' ? 'http://127.0.0.1:8000/api' : '')).trim().replace(/\/+$/, '')
  const explicitAppid = (env.MINIPROGRAM_APP_ID || '').trim()
  const appid = explicitAppid || (environment === 'development' ? String(project.appid || '').trim() : '')
  const version = (env.RELEASE_VERSION || 'unreleased').trim()
  const commit = (env.GIT_COMMIT || 'unknown').trim()
  validateBuildConfig(environment, apiBaseUrl, appid)
  validateReleaseMetadata(environment, version, commit)

  const sourceFiles = fileInventory(path.join(root, 'miniprogram')).map(file => ({ ...file, path: `miniprogram/${file.path}` }))
  sourceFiles.push({ path: 'project.config.json', size: projectBytes.length, sha256: sha256(projectBytes) })
  sourceFiles.sort(comparePaths)
  const sourceDigest = inventoryDigest(sourceFiles)
  const required = ['app.js', 'app.json', 'config.js', 'build.config.js', 'utils/api.js']
  for (const item of required) {
    if (!fs.existsSync(path.join(root, 'miniprogram', item))) throw new Error(`源码缺少 ${item}`)
  }

  project.appid = appid
  project.setting = { ...project.setting, urlCheck: environment !== 'development' }
  const output = path.join(root, 'dist', `miniprogram-${environment}`)
  fs.rmSync(output, { recursive: true, force: true })
  fs.mkdirSync(output, { recursive: true })
  fs.cpSync(path.join(root, 'miniprogram'), path.join(output, 'miniprogram'), { recursive: true })
  const generated = `module.exports = ${JSON.stringify({ environment, apiBaseUrl,
    allowRuntimeOverride: environment === 'development', version, commit }, null, 2)}\n`
  fs.writeFileSync(path.join(output, 'miniprogram', 'build.config.js'), generated)
  fs.writeFileSync(path.join(output, 'project.config.json'), `${JSON.stringify(project, null, 2)}\n`)

  // The manifest is excluded from its own inventory, avoiding recursive hashes.
  const files = fileInventory(output, new Set(['build-manifest.json']))
  fs.writeFileSync(path.join(output, 'build-manifest.json'), `${JSON.stringify({
    schemaVersion: 2, digestAlgorithm: 'sha256', environment, version, commit,
    sourceDigest, sourceFiles, artifactDigest: inventoryDigest(files), files,
    apiBaseUrl, appid, createdAt: new Date().toISOString(),
  }, null, 2)}\n`)
  return output
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const output = build(process.argv[2] || 'development')
  process.stdout.write(`${output}\n`)
}
