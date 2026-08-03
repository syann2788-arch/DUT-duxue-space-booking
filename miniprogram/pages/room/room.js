const app = getApp()
const T={free:'空闲',busy:'较满',crowded:'已满'}, C={free:'#27ae60',busy:'#e67e22',crowded:'#e0556a'}

Page({
  data: {
    room:null, statusText:'', statusColor:'', isAdmin:false, isC:false,
    todaySlots:[], allSlots:[], todayBlocks:[], timelineSegments:[], todayDate:'', totalSlots:0,
    messages:[], showPost:false, postContent:'', postPhoto:'', posting:false
  },

  onLoad(opt) {
    const d = new Date()
    const today = d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')
    const rid = opt.id
    this.setData({ todayDate: today })
    this.rid = rid

    app.call('rooms', { action:'detail', room_id:rid }).then(r => {
      if (!r) { wx.showToast({ title:'房间不存在', icon:'none' }); return setTimeout(()=>wx.navigateBack(),500) }
      this.setData({ room:r, statusText:T[r.public_status]||'空闲', statusColor:C[r.public_status]||'#27ae60',
        isAdmin: app.globalData.user?.role==='admin',
        isC: app.globalData.user?.role==='counselor'||app.globalData.user?.role==='admin' })
      if (r.can_reserve) {
        app.call('rooms', { action:'slots', room_id:rid, date:today }).then(res => {
          const all = res.slots || []
          // Merge consecutive reserved slots into blocks for timeline
          const blocks = []
          let cur = null
          all.forEach(s => {
            if (!s.available) {
              if (cur && cur.user_name === s.user_name && cur.end === s.slot) {
                cur.end = s.slot + 1
              } else {
                if (cur) blocks.push(cur)
                cur = { start: s.slot, end: s.slot + 1, user_name: s.user_name, user_class: s.user_class, people: s.people, reason: s.reason }
              }
            } else {
              if (cur) { blocks.push(cur); cur = null }
            }
          })
          if (cur) blocks.push(cur)
          // Build timeline segments: merge consecutive slots of same type+person
          const segments = []
          let seg = null
          all.forEach(s => {
            const key = s.available ? 'free' : ('r_' + s.user_name)
            if (seg && seg.key === key) {
              seg.end = s.slot + 1
            } else {
              if (seg) segments.push(seg)
              seg = { key, start: s.slot, end: s.slot + 1, available: s.available,
                user_name: s.user_name, people: s.people, reason: s.reason, user_class: s.user_class }
            }
          })
          if (seg) segments.push(seg)
          // Precompute display labels and border-radius for each block/segment
          function fmtTime(slot) { return Math.floor(8+slot/2)+':'+(slot%2===0?'00':'30') }
          const blocksOut = blocks.map(b => ({ ...b, timeLabel: fmtTime(b.start)+'-'+fmtTime(b.end) }))
          const segsOut = segments.map((s, i) => {
            let br = '0'
            const last = i === segments.length - 1
            if (i === 0 && last) br = '8rpx'
            else if (i === 0) br = '8rpx 0 0 8rpx'
            else if (last) br = '0 8rpx 8rpx 0'
            return { ...s, borderRadius: br }
          })
          this.setData({ todaySlots: all.filter(s => !s.available), allSlots: all, todayBlocks: blocksOut, timelineSegments: segsOut, totalSlots: all.length })
        }).catch(() => {})
      }
    }).catch(err => console.error(err))

    this.loadMessages()
  },

  loadMessages() {
    app.call('messages', { action:'list', room_id: this.rid }).then(data => {
      this.setData({ messages: (data||[]).map(m => ({
        ...m,
        created_at: m.created_at ? new Date(m.created_at).toLocaleDateString('zh-CN',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : ''
      })) })
    }).catch(() => {})
  },

  setStatus(e) {
    const s = e.currentTarget.dataset.s
    app.call('admin', { action:'publicStatus', room_id:this.data.room._id||this.data.room.id, public_status:s }).then(()=>{
      wx.showToast({title:'已更新',icon:'success'})
      this.setData({room:{...this.data.room,public_status:s},statusText:T[s],statusColor:C[s]})
    }).catch(err => console.error(err))
  },

  goReserve() { const r=this.data.room; wx.navigateTo({url:'/pages/reserve/reserve?roomId='+(r._id||r.id)+'&roomName='+encodeURIComponent(r.name)+'&roomCode='+encodeURIComponent(r.room_code)}) },

  showSlotInfo(e) {
    const d = e.currentTarget.dataset
    wx.showModal({
      title: '预约信息',
      content: '预约人：'+d.name+'\n班级：'+(d.class||'未填写')+'\n使用人数：'+(d.people||'?')+'人\n申请理由：'+(d.reason||'未填写'),
      showCancel: false
    })
  },

  // ── 留言板 ──
  openPost() { this.setData({ showPost:true, postContent:'', postPhoto:'' }) },
  closePost() { this.setData({ showPost:false }) },
  onPostContent(e) { this.setData({ postContent: e.detail.value }) },

  choosePhoto() {
    wx.chooseImage({ count:1, sizeType:['compressed'], sourceType:['album','camera'], success: res => {
      wx.showLoading({ title:'上传中...' })
      wx.cloud.uploadFile({ cloudPath:'messages/'+Date.now()+'.jpg', filePath:res.tempFilePaths[0] }).then(upload => {
        wx.hideLoading()
        this.setData({ postPhoto: upload.fileID })
      }).catch(() => { wx.hideLoading(); wx.showToast({ title:'上传失败', icon:'none' }) })
    }})
  },

  removePhoto() { this.setData({ postPhoto:'' }) },

  submitPost() {
    const { postContent, postPhoto } = this.data
    if (!postContent.trim() && !postPhoto) return wx.showToast({ title:'请输入留言或添加照片', icon:'none' })
    this.setData({ posting:true })
    app.call('messages', {
      action:'post', room_id:this.rid,
      content: postContent.trim(),
      photo_url: postPhoto
    }).then(() => {
      wx.showToast({ title:'发布成功', icon:'success' })
      this.setData({ showPost:false, posting:false })
      this.loadMessages()
    }).catch(() => this.setData({ posting:false }))
  },

  previewPhoto(e) {
    wx.previewImage({ urls: [e.currentTarget.dataset.url], current: e.currentTarget.dataset.url })
  }
})
