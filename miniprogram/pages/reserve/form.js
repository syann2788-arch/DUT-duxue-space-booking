const app = getApp()

const SCENE_LABELS = {
  study: '自习',
  meeting: '开会',
  event: '大型活动',
  music: '音乐练习'
}

Page({
  data: {
    scene: '',
    sceneLabel: '',
    date: '',
    startSlot: 0,
    endSlot: 0,
    timeLabel: '',
    people: 1,
    purpose: '',
    campusCardLocal: '',
    campusCardUrl: '',
    uploading: false,
    submitting: false
  },

  onLoad(options) {
    const scene = options.scene || ''
    const people = scene === 'study' ? 1 : Number(options.people)
    const startSlot = Number(options.startSlot)
    const endSlot = Number(options.endSlot)
    if (!SCENE_LABELS[scene] || !options.date || !Number.isInteger(startSlot) || !Number.isInteger(endSlot) || endSlot <= startSlot || !Number.isInteger(people) || people < 1 || people > 500) {
      wx.showToast({ title: '预约信息不完整，请重新选择', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 700)
      return
    }
    this.setData({
      scene,
      sceneLabel: SCENE_LABELS[scene],
      date: options.date,
      startSlot,
      endSlot,
      timeLabel: decodeURIComponent(options.timeLabel || ''),
      people,
      purpose: scene === 'study' ? '个人自习' : ''
    })
  },

  onPurpose(event) {
    this.setData({ purpose: event.detail.value })
  },

  chooseCampusCard() {
    if (this.data.uploading || this.data.submitting) return
    wx.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType: ['camera', 'album'],
      success: result => {
        const path = result.tempFilePaths && result.tempFilePaths[0]
        if (path) this.uploadCampusCard(path)
      }
    })
  },

  async uploadCampusCard(path) {
    const previousLocal = this.data.campusCardLocal
    const previousUrl = this.data.campusCardUrl
    this.setData({ campusCardLocal: path, campusCardUrl: '', uploading: true })
    wx.showLoading({ title: '上传玉兰卡...' })
    try {
      const result = await app.upload('/reservations/campus-card-photo', path)
      if (!result || !result.url) throw new Error('服务器未返回照片地址')
      this.setData({ campusCardUrl: result.url })
      wx.hideLoading()
      wx.showToast({ title: '玉兰卡已上传', icon: 'success' })
    } catch (err) {
      this.setData({ campusCardLocal: previousLocal, campusCardUrl: previousUrl })
      wx.hideLoading()
      wx.showToast({ title: err.message || '玉兰卡上传失败', icon: 'none' })
    } finally {
      this.setData({ uploading: false })
    }
  },

  wxLogin() {
    return new Promise((resolve, reject) => {
      wx.login({
        success: result => result.code ? resolve(result.code) : reject(new Error('未获取到微信登录凭证')),
        fail: reject
      })
    })
  },

  requestSubscription(templateIds) {
    return new Promise(resolve => {
      wx.requestSubscribeMessage({
        tmplIds: templateIds,
        complete: resolve
      })
    })
  },

  async setupWechatNotifications() {
    try {
      const code = await this.wxLogin()
      await app.request('/auth/wechat/bind', {
        method: 'POST',
        data: { code }
      })
      const result = await app.request('/notifications/templates')
      const templateIds = Array.isArray(result.template_ids) ? result.template_ids.filter(Boolean) : []
      for (let index = 0; index < templateIds.length; index += 3) {
        await this.requestSubscription(templateIds.slice(index, index + 3))
      }
    } catch (err) {
      console.warn('订阅消息设置未完成，不影响预约提交', err)
    }
  },

  async submit() {
    if (this.data.submitting || this.data.uploading) return
    const isStudy = this.data.scene === 'study'
    const purpose = isStudy ? '个人自习' : this.data.purpose.trim()
    if (!isStudy && purpose.length < 10) {
      wx.showToast({ title: '申请用途至少填写10个字', icon: 'none' })
      return
    }
    if (!this.data.campusCardUrl) {
      wx.showToast({ title: '请先上传本人玉兰卡照片', icon: 'none' })
      return
    }

    this.setData({ submitting: true })
    let loadingShown = false
    let reservation = null
    try {
      await this.setupWechatNotifications()
      wx.showLoading({ title: '提交预约...' })
      loadingShown = true
      reservation = await app.request('/reservations', {
        method: 'POST',
        data: {
          scene: this.data.scene,
          date: this.data.date,
          start_slot: this.data.startSlot,
          end_slot: this.data.endSlot,
          people_count: isStudy ? 1 : this.data.people,
          purpose,
          campus_card_photo_url: this.data.campusCardUrl
        }
      })
    } catch (err) {
      wx.showToast({ title: err.message || '预约提交失败', icon: 'none', duration: 2500 })
    } finally {
      if (loadingShown) wx.hideLoading()
      this.setData({ submitting: false })
    }

    if (!reservation) return
    const room = reservation.room || {}
    const roomText = [room.room_code, room.name].filter(Boolean).join(' ')
    wx.showModal({
      title: '提交成功',
      content: roomText ? '已分配 ' + roomText + '，等待审核' : '预约申请已提交，等待审核',
      showCancel: false,
      success: () => wx.switchTab({ url: '/pages/my/my' })
    })
  }
})
