App({
  globalData: {
    token: '',
    user: null
  },

  onLaunch() {
    wx.cloud.init({ env: wx.cloud.DYNAMIC_CURRENT_ENV, traceUser: true })
    this.autoLogin()
  },

  // Try WeChat auto-login first, fall back to stored token
  autoLogin() {
    this.call('auth', { action: 'wechatLogin' }).then(res => {
      this.setLogin(res.token, res.user)
    }).catch(() => {
      // Not bound yet, try stored token
      const token = wx.getStorageSync('token')
      if (token) {
        this.globalData.token = token
        this.call('auth', { action: 'me', token }).then(u => {
          this.setLogin(token, u)
        }).catch(() => {
          this.globalData.token = ''
          wx.removeStorageSync('token')
        })
      }
    })
  },

  setLogin(token, user) {
    this.globalData.token = token
    this.globalData.user = user
    wx.setStorageSync('token', token)
  },

  logout() {
    this.globalData.token = ''
    this.globalData.user = null
    wx.removeStorageSync('token')
    wx.reLaunch({ url: '/pages/login/login' })
  },

  // Unified cloud function caller
  call(name, data = {}) {
    if (name !== 'auth') data.token = this.globalData.token
    return wx.cloud.callFunction({ name, data }).then(res => {
      if (res.result && res.result.err) {
        wx.showToast({ title: res.result.err, icon: 'none' })
        if (res.result.err === '未登录' || res.result.err === '登录已过期') {
          this.logout()
        }
        throw new Error(res.result.err)
      }
      return res.result
    })
  }
})
