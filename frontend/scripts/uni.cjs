const fs = require('fs')
const path = require('path')

// The historical HBuilderX project keeps manifest.json/pages.json at project
// root. Uni CLI defaults to ./src, so provide an absolute input directory.
const projectDir = process.cwd()
const inputDir = path.join(projectDir, '.uni-src', String(process.pid))
fs.mkdirSync(inputDir, { recursive: true })
function copy(source, target) {
  const stat = fs.statSync(source)
  if (stat.isDirectory()) {
    fs.mkdirSync(target, { recursive: true })
    for (const child of fs.readdirSync(source)) copy(path.join(source, child), path.join(target, child))
  } else {
    fs.copyFileSync(source, target)
  }
}
for (const name of ['App.vue', 'main.js', 'manifest.json', 'pages.json', 'uni.scss', 'index.html', 'api', 'pages', 'static', 'store']) {
  copy(path.join(projectDir, name), path.join(inputDir, name))
}
process.env.UNI_INPUT_DIR = inputDir
const packageFile = require.resolve('@dcloudio/vite-plugin-uni/package.json')
require(path.join(path.dirname(packageFile), 'bin', 'uni.js'))
