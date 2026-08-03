const app = getApp()

Page({
  data: { id: '', pw: '', loading: false },

  onLoad() {
    // Already logged in via token? Skip to index
    const token = wx.getStorageSync('token')
    if (token) {
      app.call('auth', { action: 'me', token }).then(u => {
        if (!u.err) {
          app.setLogin(token, u)
          wx.switchTab({ url: '/pages/index/index' })
        }
      }).catch(err => console.error('autoLogin check failed', err))
    }
  },

  onId(e) { this.setData({ id: e.detail.value }) },
  onPass(e) { this.setData({ pw: e.detail.value }) },

  doLogin() {
    const { id, pw } = this.data
    if (!id || !pw) return wx.showToast({ title: '请填写学号和密码', icon: 'none' })
    this.setData({ loading: true })
    app.call('auth', { action:'login', student_id:id, password:pw }).then(res => {
      app.setLogin(res.token, res.user)
      wx.switchTab({ url: '/pages/index/index' })
    }).catch(err => console.error('login failed', err)).finally(() => this.setData({ loading: false }))
  },

  goRegister() { wx.navigateTo({ url: '/pages/login/register' }) },
  goForgot() { wx.navigateTo({ url: '/pages/login/forgot' }) }
})
