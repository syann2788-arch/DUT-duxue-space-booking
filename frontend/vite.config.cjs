const { defineConfig } = require('vite')
const uniModule = require('@dcloudio/vite-plugin-uni')
const uni = uniModule.default || uniModule

module.exports = defineConfig({ plugins: [uni()] })
