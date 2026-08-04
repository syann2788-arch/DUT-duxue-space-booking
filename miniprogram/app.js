const api = require('./utils/api')

App({
  globalData: {
    token: '',
    user: null
  },

  authReady: null,
  _authAttemptId: 0,

  onLaunch() {
    const attemptId = ++this._authAttemptId
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
      this.authReady = this.request('/auth/me').then(user => {
        if (attemptId !== this._authAttemptId) return null
        this.setLogin(token, user)
        return user
      }).catch(err => {
        if (attemptId === this._authAttemptId && err.statusCode === 401) this.clearLogin()
        return null
      })
      return
    }

    this.authReady = this.getWechatCode().then(code => {
      return this.request('/auth/wechat/login', { method: 'POST', data: { code } })
    }).then(result => {
      if (attemptId !== this._authAttemptId) return null
      this.setLogin(result.access_token, result.user)
      return result.user
    }).catch(() => null)
  },

  getWechatCode() {
    return new Promise((resolve, reject) => {
      wx.login({
        success: result => result.code ? resolve(result.code) : reject(new Error('未获取到微信登录凭证')),
        fail: reject
      })
    })
  },

  prepareInteractiveLogin() {
    this._authAttemptId += 1
    this.authReady = Promise.resolve(null)
    return this.authReady
  },

  bindWechatInBackground() {
    return this.getWechatCode().then(code => {
      return this.request('/auth/wechat/bind', { method: 'POST', data: { code } })
    }).catch(() => null)
  },

  setLogin(token, user) {
    this.globalData.token = token
    this.globalData.user = user
    this.authReady = Promise.resolve(user || null)
    wx.setStorageSync('token', token)
  },

  clearLogin() {
    this.globalData.token = ''
    this.globalData.user = null
    this.authReady = Promise.resolve(null)
    wx.removeStorageSync('token')
    wx.removeStorageSync('user')
  },

  logout() {
    this._authAttemptId += 1
    this.clearLogin()
    wx.reLaunch({ url: '/pages/login/login' })
  },

  request(path, options) {
    return api.request(path, options)
  },

  upload(path, filePath, options) {
    return api.uploadFile(path, filePath, options)
  }
})
