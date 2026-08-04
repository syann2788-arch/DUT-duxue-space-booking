Page({
  contactAdmin() {
    wx.showModal({
      title: '联系书院管理员',
      content: '学校短信服务尚未接入。为保护账号安全，请联系辅导员或书院管理员核验身份后重置密码。',
      showCancel: false
    })
  },

  goBack() { wx.navigateBack() }
})
