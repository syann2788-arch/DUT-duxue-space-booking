const app = getApp()

Page({
  data: { roomId:'', roomName:'', roomCode:'', date:'', startSlot:0, endSlot:0, timeLabel:'', people:1, reason:'', notes:'', submitting:false },

  onLoad(opt) {
    this.setData({
      roomId: opt.roomId,
      roomName: decodeURIComponent(opt.roomName||''),
      roomCode: decodeURIComponent(opt.roomCode||''),
      date: opt.date,
      startSlot: +opt.startSlot,
      endSlot: +opt.endSlot,
      timeLabel: decodeURIComponent(opt.timeLabel||'')
    })
  },

  onPeople(e) { this.setData({ people: +e.detail.value }) },
  onReason(e) { this.setData({ reason: e.detail.value }) },
  onNotes(e) { this.setData({ notes: e.detail.value }) },

  submit() {
    const { roomId, date, startSlot, endSlot, people, reason, notes } = this.data
    if (!people || people < 1) { wx.showToast({ title:'请填写使用人数', icon:'none' }); return }
    if (!reason.trim()) { wx.showToast({ title:'请填写申请理由', icon:'none' }); return }

    const doCreate = () => {
      this.setData({ submitting:true })
      wx.showLoading({ title:'提交中...' })
      app.call('reservations', {
        action: 'create', room_id: roomId, date, start_slot: startSlot, end_slot: endSlot,
        people_count: people, reason: reason.trim(), notes: notes.trim()
      }).then(() => {
        wx.hideLoading()
        wx.showToast({ title:'预约成功', icon:'success' })
        setTimeout(() => { wx.switchTab({ url:'/pages/index/index' }) }, 500)
      }).catch(err => {
        wx.hideLoading()
        if (err && err.errMsg && err.errMsg.includes('fail')) {
          wx.showToast({ title: '网络异常，请检查云函数是否已部署', icon: 'none' })
        }
      }).finally(() => this.setData({ submitting:false }))
    }

    wx.requestSubscribeMessage({
      tmplIds: ['JCFEQMxQbFljZcjHgj_Nwg5pwS8HyzOcGMavkuzGEDg'],
      success: () => doCreate(),
      fail: () => doCreate()
    })
  }
})
