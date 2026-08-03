const app = getApp()
const ST = {free:'空闲',busy:'较满',crowded:'已满'}

Page({
  data: { user:{}, topRow:[], bottomRow:[], reservable:[], publics:[] },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 })
    }
    this.setData({ user: app.globalData.user||{} })
    const self = this
    Promise.all([
      app.call('rooms', { action:'list' }),
      app.call('rooms', { action:'todaySummary' }).catch(() => ({}))
    ]).then(([rooms, summary]) => {
      const map = {}; rooms.forEach(r => map[r.room_code]=r)
      function heat(code) {
        const r = map[code]
        if (!r) return ''
        const id = r._id || r.id
        const s = summary[id]
        if (!s) return ''
        if (s.pct >= 80) return 'hot'
        if (s.pct >= 40) return 'warm'
        return ''
      }
      function c(code) {
        const r = map[code]; if (!r) return {code, name:'', cls:'nonpub', tagCls:'', tag:'', canReserve:false, isPublic:false, id:'', hot:''}
        let cls='nonpub', tag='', tc=''
        if (r.can_reserve) { cls='res'; tc=r.who_can_reserve==='counselor'?'tag-cou':'tag-res'; tag=r.who_can_reserve==='counselor'?'辅导员':'可预约' }
        else if (r.is_public) { cls='pub'; tc='tag-pub'; tag=ST[r.public_status]||'空闲' }
        else { tc='tag-gray'; tag='非公共' }
        return {code:r.room_code, name:r.name, cls, tagCls:tc, tag, canReserve:r.can_reserve, isPublic:r.is_public, id:r._id||r.id, hot:heat(code)}
      }
      const purp={A101:'创新空间 · 科创实践', A103:'大剧场 · 讲座演出', A105:'会议室 · 小组讨论', A106:'谈心室 · 师生交谈 · 仅限辅导员', B102:'器乐室 · 器乐练习'}
      const pp={A102:'图书自习 · 自由阅览', A104:'生活空间 · 就餐休息'}
      const rv = ['A101','A103','A105','A106','B102'].map(k=>{const r=map[k]; return r?{id:r._id||r.id,code:r.room_code,name:r.name,desc:purp[k]}:null}).filter(Boolean)
      const pb = ['A102','A104'].map(k=>{const r=map[k]; return r?{id:r._id||r.id,code:r.room_code,name:r.name,desc:pp[k]}:null}).filter(Boolean)
      this.setData({
        topRow: ['A101','A103','C103','C101'].map(c),
        bottomRow: ['A102','A104','A105','A106','B101','B102','C102','C104'].map(c),
        reservable: rv, publics: pb
      })
    }).catch(err => console.error(err))
  },

  onCell(e) { const d=e.currentTarget.dataset; if (d.res||d.pub) wx.navigateTo({url:'/pages/room/room?id='+d.id}) },
  onRoom(e) { wx.navigateTo({url:'/pages/room/room?id='+e.currentTarget.dataset.id}) },
  doLogout() { app.logout() }
})
