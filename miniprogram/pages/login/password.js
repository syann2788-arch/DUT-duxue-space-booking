const app = getApp()
Page({
  data: { mode: 'reset', credential: '', currentPassword: '', newPassword: '', confirmPassword: '', busy: false },
  onLoad(options) { this.setData({ mode: options.mode === 'change' ? 'change' : 'reset' }) },
  onInput(e) { this.setData({ [e.currentTarget.dataset.field]: e.detail.value }) },
  async submit() {
    if (this.data.busy) return
    const { mode, credential, currentPassword, newPassword, confirmPassword } = this.data
    if (newPassword.length < 8 || !/[A-Za-z]/.test(newPassword) || !/[0-9]/.test(newPassword) || newPassword !== confirmPassword) return wx.showToast({ title: '密码需至少8位字母数字，两次一致', icon: 'none' })
    this.setData({ busy: true })
    try {
      await app.request('/auth/password/' + mode, { method: 'POST', data: mode === 'reset' ? { credential: credential.trim(), new_password: newPassword } : { current_password: currentPassword, new_password: newPassword } })
      this.setData({ credential: '', currentPassword: '', newPassword: '', confirmPassword: '' })
      app.clearLogin()
      wx.showModal({ title: '密码已更新', content: '请使用新密码重新登录。', showCancel: false, success: () => wx.reLaunch({ url: '/pages/login/login' }) })
    } catch (error) { wx.showToast({ title: error.message || '设置失败', icon: 'none' }) }
    finally { this.setData({ busy: false }) }
  }
})