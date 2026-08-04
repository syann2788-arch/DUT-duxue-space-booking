const app = getApp()

Page({
  data: { l: false, f_student_id:'', f_name:'', f_phone:'', f_class_name:'', f_password:'' },

  onF(e) { this.setData({ ['f_'+e.currentTarget.dataset.key]: e.detail.value }) },

  doRegister() {
    if (this.data.l) return
    const f = {
      student_id: this.data.f_student_id.trim(),
      name: this.data.f_name.trim(),
      phone: this.data.f_phone.trim(),
      class_name: this.data.f_class_name.trim(),
      password: this.data.f_password
    }
    if (!f.student_id||!f.name||!f.phone||!f.class_name||!f.password) return wx.showToast({title:'请填写所有字段',icon:'none'})
    if (f.password.length<6) return wx.showToast({title:'密码至少6位',icon:'none'})
    if (!/[a-zA-Z]/.test(f.password)||!/[0-9]/.test(f.password)) return wx.showToast({title:'密码需同时含字母和数字',icon:'none'})
    if (!/^\d{4}$/.test(f.class_name)) return wx.showToast({title:'班级为4位数字',icon:'none'})
    this.setData({ l: true })
    app.prepareInteractiveLogin().then(() => {
      return app.request('/auth/register', { method: 'POST', data: f })
    }).then(res => {
      app.setLogin(res.access_token, res.user)
      app.bindWechatInBackground()
      wx.switchTab({ url: '/pages/index/index' })
    }).catch(err => {
      wx.showToast({ title: err.message || '注册失败', icon: 'none' })
    }).finally(()=>this.setData({l:false}))
  },

  goBack() { wx.navigateBack() }
})
