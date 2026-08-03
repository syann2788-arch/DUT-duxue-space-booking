const app = getApp()

Page({
  data: { l: false, f_student_id:'', f_name:'', f_phone:'', f_class_name:'', f_password:'' },

  onF(e) { this.setData({ ['f_'+e.currentTarget.dataset.key]: e.detail.value }) },

  doRegister() {
    const f = { student_id: this.data.f_student_id, name: this.data.f_name, phone: this.data.f_phone, class_name: this.data.f_class_name, password: this.data.f_password }
    if (!f.student_id||!f.name||!f.phone||!f.class_name||!f.password) return wx.showToast({title:'请填写所有字段',icon:'none'})
    if (f.password.length<6) return wx.showToast({title:'密码至少6位',icon:'none'})
    if (!/[a-zA-Z]/.test(f.password)||!/[0-9]/.test(f.password)) return wx.showToast({title:'密码需同时含字母和数字',icon:'none'})
    if (!/^\d{4}$/.test(f.class_name)) return wx.showToast({title:'班级为4位数字',icon:'none'})
    this.setData({ l: true })
    app.call('auth', { action:'register', ...f }).then(res => {
      app.globalData.token = res.token
      app.globalData.user = res.user
      wx.setStorageSync('token', res.token)
      wx.switchTab({ url: '/pages/index/index' })
    }).catch(err => console.error(err)).finally(()=>this.setData({l:false}))
  },

  goBack() { wx.navigateBack() }
})
