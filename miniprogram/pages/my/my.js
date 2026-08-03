const app = getApp()
const L={active:'待签到',checked_in:'已签到',missed:'违约',cancelled:'已取消'}
const S={active:'background:#f5eef9;color:#6b2d8e',checked_in:'background:#e6f5e9;color:#2e7d32',missed:'background:#fdecea;color:#c0392b',cancelled:'background:#f5f5f5;color:#bbb'}

Page({
  data: { user:{}, isAdmin:false, isC:false, filter:'all', list:[], raw:[], counselorCount:0 },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 })
    }
    const role = app.globalData.user?.role
    this.setData({ user: app.globalData.user||{}, isAdmin: role==='admin', isC: role==='counselor'||role==='admin' })
    // Check missed first, then load
    app.call('reservations', { action:'checkMissed' }).then(() => {
      return app.call('reservations', { action:'my' })
    }).then(data => {
      const now = new Date()
      const O = 8 // openHour
      const raw = (data||[]).map(r => {
        const base = new Date(r.date + 'T00:00:00+08:00').getTime()
        const start = new Date(base + O * 3600000 + (r.start_slot || 0) * 30 * 60000)
        const end = new Date(base + O * 3600000 + (r.end_slot || 0) * 30 * 60000)
        const ss = r.start_slot || 0, es = r.end_slot || 0
        const st = O * 60 + ss * 30, et = O * 60 + es * 30
        const timeLabel = String(Math.floor(st/60)).padStart(2,'0')+':'+String(st%60).padStart(2,'0')+'-'+String(Math.floor(et/60)).padStart(2,'0')+':'+String(et%60).padStart(2,'0')
        return { ...r, id: r._id, room_code:r.room?.room_code||'?', room_name:r.room?.name||'',
          timeLabel,
          people: r.people_count||1, reason: r.reason||'', notes: r.notes||'',
          statLabel:L[r.status]||r.status, statStyle:S[r.status]||'',
          canCheckin: r.status==='active'&&now>=start&&now<=new Date(start.getTime()+15*60000),
          canCancel: r.status==='active'&&now<new Date(start.getTime()-30*60000) }
      })
      const cCount = raw.filter(r => r.room_code === 'A106').length
      this.setData({raw, counselorCount: cCount},()=>this.applyFilter())
    }).catch(err => console.error(err))
  },

  setFilter(e) { this.setData({filter:e.currentTarget.dataset.f},()=>this.applyFilter()) },
  applyFilter() { const f=this.data.filter; this.setData({list:f==='all'?this.data.raw:this.data.raw.filter(r=>r.status===f)}) },

  doCheckin(e) {
    app.call('reservations', {action:'checkin',reservation_id:e.currentTarget.dataset.id}).then(()=>{wx.showToast({title:'签到成功',icon:'success'});this.onShow()}).catch(err => console.error(err))
  },
  doCancel(e) {
    wx.showModal({title:'确认取消',content:'确定取消吗？',success:res=>{if(!res.confirm)return;app.call('reservations',{action:'cancel',reservation_id:e.currentTarget.dataset.id}).then(()=>{wx.showToast({title:'已取消',icon:'success'});this.onShow()}).catch(err => console.error(err))}})
  },
  goAdmin() { wx.navigateTo({url:'/pages/admin/admin'}) },

  scanCheckin() {
    wx.scanCode({ onlyFromCamera: true, success: res => {
      let roomId = ''
      try {
        const data = JSON.parse(res.result)
        roomId = data.room_id || data.roomId || ''
      } catch {
        // Plain text: room ID directly
        roomId = res.result.trim()
      }
      if (!roomId) return wx.showToast({ title: '无效的房间码', icon: 'none' })
      // Find active reservation for this room
      const match = this.data.raw.find(r => r.status === 'active' && r.room_id === roomId)
      if (!match) return wx.showToast({ title: '未找到该房间的待签到预约', icon: 'none' })
      app.call('reservations', { action: 'checkin', reservation_id: match._id || match.id }).then(() => {
        wx.showToast({ title: '签到成功', icon: 'success' })
        this.onShow()
      }).catch(() => {})
    }})
  },

  rebook(e) {
    const r = e.currentTarget.dataset.item
    if (!r || !r.room) return
    wx.navigateTo({
      url: '/pages/reserve/reserve?roomId=' + (r.room_id) +
        '&roomName=' + encodeURIComponent(r.room.room_code + ' ' + (r.room.name || '')) +
        '&roomCode=' + encodeURIComponent(r.room.room_code || '')
    })
  }
})
