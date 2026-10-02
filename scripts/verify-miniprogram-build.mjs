import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { fileInventory, inventoryDigest, validateBuildConfig, validateReleaseMetadata } from './build-miniprogram.mjs'

export function verifyBuild(directory) {
  const manifest = JSON.parse(fs.readFileSync(path.join(directory, 'build-manifest.json'), 'utf8'))
  if (manifest.schemaVersion !== 2 || manifest.digestAlgorithm !== 'sha256') {
    throw new Error('不支持的构建清单版本或摘要算法')
  }
  validateBuildConfig(manifest.environment, manifest.apiBaseUrl, manifest.appid)
  validateReleaseMetadata(manifest.environment, manifest.version, manifest.commit)
  const actual = fileInventory(directory, new Set(['build-manifest.json']))
  if (JSON.stringify(actual) !== JSON.stringify(manifest.files) || inventoryDigest(actual) !== manifest.artifactDigest) {
    throw new Error('构建目录与清单不一致：存在缺失、新增或修改的文件')
  }
  if (!Array.isArray(manifest.sourceFiles) || inventoryDigest(manifest.sourceFiles) !== manifest.sourceDigest) {
    throw new Error('源码清单与源码摘要不一致')
  }
  return manifest
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  if (!process.argv[2]) throw new Error('用法: node scripts/verify-miniprogram-build.mjs <构建目录>')
  const manifest = verifyBuild(path.resolve(process.argv[2]))
  process.stdout.write(`校验通过: ${manifest.environment} ${manifest.version} ${manifest.commit}\n${manifest.artifactDigest}\n`)
}
