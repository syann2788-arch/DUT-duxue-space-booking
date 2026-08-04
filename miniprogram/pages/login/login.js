const app = getApp()

Page({
  data: { id: '', pw: '', loading: false },

  onLoad() {
    this._manualLogin = false
    this._navigated = false
    this._unloaded = false
    this._visible = true
    Promise.resolve(app.authReady).then(user => {
      if (user && !this._manualLogin && !this._unloaded && this._visible) this.enterHome()
    })
  },

  onShow() {
    this._visible = true
    if (app.globalData.user && !this._manualLogin) this.enterHome()
  },

  onHide() {
    this._visible = false
  },

  onUnload() {
    this._unloaded = true
    this._visible = false
  },

  onId(e) { this.setData({ id: e.detail.value }) },
  onPass(e) { this.setData({ pw: e.detail.value }) },

  doLogin() {
    if (this.data.loading) return
    const id = this.data.id.trim()
    const pw = this.data.pw
    if (!id || !pw) return wx.showToast({ title: '请填写学号和密码', icon: 'none' })
    this._manualLogin = true
    this.setData({ loading: true })
    app.prepareInteractiveLogin().then(() => app.request('/auth/login', {
      method: 'POST',
      data: { student_id: id, password: pw }
    })).then(res => {
      app.setLogin(res.access_token, res.user)
      app.bindWechatInBackground()
      this.enterHome()
    }).catch(err => {
      wx.showToast({ title: err.message || '登录失败', icon: 'none' })
    }).finally(() => this.setData({ loading: false }))
  },

  enterHome() {
    if (this._navigated || this._unloaded || !this._visible) return
    this._navigated = true
    wx.switchTab({ url: '/pages/index/index' })
  },

  goRegister() { wx.navigateTo({ url: '/pages/login/register' }) },
  goForgot() { wx.navigateTo({ url: '/pages/login/forgot' }) }
})
