const app = getApp()

Page({
  data: { phone:'', code:'', newPw:'', confirmPw:'', sending:false, countdown:0, submitting:false },

  onUnload() { if (this._timer) clearInterval(this._timer) },

  onPhone(e) { this.setData({ phone: e.detail.value }) },
  onCode(e) { this.setData({ code: e.detail.value }) },
  onPw(e) { this.setData({ newPw: e.detail.value }) },
  onConfirmPw(e) { this.setData({ confirmPw: e.detail.value }) },

  sendCode() {
    const { phone } = this.data
    if (!phone || !/^\d{11}$/.test(phone)) return wx.showToast({ title:'请输入正确手机号', icon:'none' })
    this.setData({ sending:true })
    app.call('auth', { action:'sendCode', phone }).then(res => {
      wx.showToast({ title: res.msg || '验证码已发送', icon:'none', duration:2000 })
      let cd = 60
      this.setData({ countdown: cd })
      this._timer = setInterval(() => {
        cd--; if (cd <= 0) { clearInterval(this._timer); this.setData({ countdown:0 }) }
        else this.setData({ countdown: cd })
      }, 1000)
    }).catch(err => console.error('sendCode failed', err)).finally(() => this.setData({ sending:false }))
  },

  reset() {
    const { phone, code, newPw, confirmPw } = this.data
    if (!phone || !code || !newPw || !confirmPw) return wx.showToast({ title:'请填写完整信息', icon:'none' })
    if (newPw !== confirmPw) return wx.showToast({ title:'两次输入的新密码不一致', icon:'none' })
    this.setData({ submitting:true })
    app.call('auth', { action:'resetPassword', phone, code, new_password: newPw }).then(() => {
      wx.showToast({ title:'密码重置成功，请登录', icon:'success' })
      setTimeout(() => wx.navigateBack(), 800)
    }).catch(err => console.error('resetPassword failed', err)).finally(() => this.setData({ submitting:false }))
  },

  goBack() { wx.navigateBack() }
})
