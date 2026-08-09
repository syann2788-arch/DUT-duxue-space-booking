const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

test('my-page reservation action stays above the custom tab bar and iOS safe area', () => {
  const stylesheet = fs.readFileSync(
    path.join(__dirname, '..', 'pages', 'my', 'my.wxss'),
    'utf8'
  )

  assert.match(stylesheet, /bottom:\s*calc\(124rpx \+ env\(safe-area-inset-bottom\)\)/)
  assert.match(stylesheet, /padding-bottom:\s*calc\(224rpx \+ env\(safe-area-inset-bottom\)\)/)
  assert.match(stylesheet, /\.reserve-fab\s*\{[\s\S]*?z-index:\s*20;/)
})

test('device-debug package excludes transient pytest cache paths', () => {
  const projectConfig = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', '..', 'project.config.json'),
    'utf8'
  ))
  const ignored = projectConfig.packOptions && projectConfig.packOptions.ignore

  assert.ok(Array.isArray(ignored))
  assert.ok(ignored.some(item => item.type === 'folder' && item.value === '.pytest_cache'))
  assert.ok(ignored.some(item => item.type === 'prefix' && item.value === 'pytest-cache-files-'))
})
