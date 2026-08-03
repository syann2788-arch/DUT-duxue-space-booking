const app = getApp()
const C = { openHour:8, closeHour:22, slotMinutes:30, maxSlots:8 }

Page({
  data: { roomId:'', roomName:'', roomCode:'', dateStr:'', dateLabel:'今天', currentTs:0, slots:[], selected:[], loading:false, showInfo:false, infoData:{} },

  onLoad(opt) {
    const d = new Date(); d.setHours(0,0,0,0)
    const dateStr = this.fmt(d)
    this.setData({ roomId:opt.roomId, roomName:decodeURIComponent(opt.roomName||''), roomCode:decodeURIComponent(opt.roomCode||''), currentTs:d.getTime(), dateStr, dateLabel:'今天' })
    this.loadSlots()
  },

  fmt(d) { return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0') },

  loadSlots() {
    const { roomId, dateStr } = this.data
    if (!roomId) { wx.showToast({ title:'房间信息异常', icon:'none' }); return }
    this.setData({ loading:true })
    wx.showLoading({ title:'加载中...' })
    app.call('rooms', { action:'slots', room_id:roomId, date:dateStr }).then(res => {
      wx.hideLoading()
      const slots = (res.slots||[]).map(s => ({ ...s, selected: false }))
      this.setData({ slots, selected:[], loading:false })
    }).catch(err => {
      wx.hideLoading()
      console.error('loadSlots', err)
      this.setData({ loading:false })
      wx.showToast({ title:'加载时段失败', icon:'none' })
    })
  },

  changeDate(e) {
    const delta = +e.currentTarget.dataset.d
    const d = new Date(this.data.currentTs)
    d.setDate(d.getDate() + delta)
    d.setHours(0,0,0,0)
    const today = new Date(); today.setHours(0,0,0,0)
    const max = new Date(today); max.setDate(max.getDate()+1)
    const ds = this.fmt(d), ts = this.fmt(today), ms = this.fmt(max)
    if (ds < ts || ds > ms) { wx.showToast({ title:'仅可提前1天预约', icon:'none' }); return }
    this.setData({ currentTs:d.getTime(), dateStr:ds, dateLabel: ds===ts?'今天':ds===ms?'明天':'' })
    this.loadSlots()
  },

  toggle(e) {
    const { slot:clicked, avail } = e.currentTarget.dataset
    if (!avail) {
      const { name, class:className, people, reason } = e.currentTarget.dataset
      this.setData({ showInfo:true, infoData:{ name, class_name:className, people, reason: reason||'' } })
      return
    }
    const sel = [...this.data.selected]
    const idx = sel.indexOf(clicked)
    const slotMap = {}; this.data.slots.forEach(s => { slotMap[s.slot] = s.available })

    if (idx >= 0) {
      if (idx === 0 || idx === sel.length - 1) sel.splice(idx, 1)
      else return wx.showToast({ title:'只能从两端取消', icon:'none' })
    } else {
      if (!sel.length) { sel.push(clicked) }
      else {
        const min = Math.min(...sel), max = Math.max(...sel)
        if (clicked >= min && clicked <= max) return
        let from, to
        if (clicked < min) { from = clicked; to = min - 1 }
        else { from = max + 1; to = clicked }
        for (let s = from; s <= to; s++) {
          if (!slotMap[s]) return wx.showToast({ title:'所选范围包含已约时段', icon:'none' })
          sel.push(s)
        }
      }
      sel.sort((a,b) => a-b)
      if (sel.length > C.maxSlots) return wx.showToast({ title:'单次最多'+C.maxSlots/2+'小时', icon:'none' })
    }

    const slots = this.data.slots.map(s => ({...s, selected: sel.includes(s.slot)}))
    this.setData({ slots, selected: sel })
  },

  nextStep() {
    const sel = this.data.selected
    if (!sel.length) return
    const start = Math.min(...sel)
    const end = Math.max(...sel) + 1
    const fromMin = C.openHour * 60 + start * C.slotMinutes
    const toMin = C.openHour * 60 + end * C.slotMinutes
    const fh = Math.floor(fromMin / 60), fm = fromMin % 60
    const th = Math.floor(toMin / 60), tm = toMin % 60
    const timeLabel = String(fh).padStart(2,'0')+':'+String(fm).padStart(2,'0')+'-'+String(th).padStart(2,'0')+':'+String(tm).padStart(2,'0')
    wx.navigateTo({ url:'/pages/reserve/form?roomId='+this.data.roomId+'&roomName='+encodeURIComponent(this.data.roomName)+'&roomCode='+encodeURIComponent(this.data.roomCode)+'&date='+this.data.dateStr+'&startSlot='+start+'&endSlot='+end+'&timeLabel='+encodeURIComponent(timeLabel) })
  },

  closeInfo() { this.setData({ showInfo:false }) }
})
