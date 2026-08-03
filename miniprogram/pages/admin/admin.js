const app = getApp()
const R = {student:'学生',counselor:'辅导员',admin:'管理员'}

Page({
  data: { stats:{}, users:[], rooms:[] },
  onShow() {
    if (app.globalData.user?.role!=='admin') { wx.showToast({title:'无权限',icon:'none'}); return setTimeout(()=>wx.navigateBack(),500) }
    app.call('admin', { action:'stats' }).then(stats => {
      this.setData({ stats: stats || {} })
    }).catch(() => {})
    app.call('admin', { action:'users' }).then(users => {
      this.setData({users:users.map(u=>({id:u.id,student_id:u.student_id,name:u.name,phone:u.phone,class_name:u.class_name,role:u.role,is_active:u.is_active,banned_until:u.banned_until,rl:R[u.role]||u.role,bl:u.banned_until?new Date(u.banned_until).toLocaleString():''}))})
    }).catch(err => console.error(err))
    app.call('rooms', { action:'list' }).then(rooms => {
      this.setData({ rooms: rooms.filter(r => r.can_reserve).map(r => ({ id: r._id, code: r.room_code, name: r.name })) })
    }).catch(() => {})
  },
  doBan(e) { const{id,name}=e.currentTarget.dataset; wx.showModal({title:'禁约',content:'确定禁约 '+name+' 7天？',success:res=>{if(!res.confirm)return;app.call('admin',{action:'ban',user_id:id,days:7}).then(()=>{wx.showToast({title:'已禁约',icon:'success'});this.onShow()}).catch(err=>console.error(err))}}) },
  doUnban(e) { app.call('admin',{action:'unban',user_id:e.currentTarget.dataset.id}).then(()=>{wx.showToast({title:'已解禁',icon:'success'});this.onShow()}).catch(err=>console.error(err)) },

  copyRoomCode(e) {
    const code = JSON.stringify({ room_id: e.currentTarget.dataset.id })
    wx.setClipboardData({ data: code, success: () => wx.showToast({ title:'已复制，去生成二维码吧', icon:'none' }) })
  },

  exportCSV() {
    wx.showLoading({ title:'生成中...' })
    app.call('admin', { action:'export' }).then(res => {
      wx.hideLoading()
      if (!res.csv) return wx.showToast({ title:'暂无数据', icon:'none' })
      // Copy to clipboard (practical for WeChat)
      wx.setClipboardData({ data: res.csv, success: () => {
        wx.showToast({ title:'已复制到剪贴板，可粘贴到Excel', icon:'none', duration:3000 })
      }})
    }).catch(() => { wx.hideLoading(); wx.showToast({ title:'导出失败', icon:'none' }) })
  }
})
