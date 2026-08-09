// Development defaults only. The build script replaces this file in dist/.
module.exports = {
  environment: 'development',
  version: 'dev',
  commit: 'local',
  apiBaseUrls: {
    develop: 'http://127.0.0.1:8000/api',
    trial: '',
    release: ''
  }
}
