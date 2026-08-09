const { spawnSync } = require('node:child_process')
const { readdirSync } = require('node:fs')
const { join } = require('node:path')

const root = join(__dirname, '..')
const excluded = new Set(['node_modules'])

function files(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return excluded.has(entry.name) ? [] : files(path)
    return entry.isFile() && entry.name.endsWith('.js') ? [path] : []
  })
}

for (const file of files(root)) {
  const result = spawnSync(process.execPath, ['--check', file], { stdio: 'inherit' })
  if (result.status !== 0) process.exit(result.status || 1)
}
