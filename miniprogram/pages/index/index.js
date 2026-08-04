const app = getApp()

const STATUS_TEXT = { free: '空闲', busy: '较满', crowded: '已满' }
const TOP_CODES = ['A101', 'A103', 'C103', 'C101']
const BOTTOM_CODES = ['A102', 'A104', 'A105', 'A106', 'B101', 'B102', 'C102', 'C104']
const RESERVABLE_CODES = ['A101', 'A102', 'A103', 'A105', 'A106', 'B102']
const PUBLIC_CODES = ['A102', 'A104']

function listItem(room) {
  return {
    id: room.id,
    code: room.room_code,
    name: room.name,
    desc: room.description || room.category || ''
  }
}

Page({
  data: {
    user: {},
    topRow: [],
    bottomRow: [],
    reservable: [],
    publics: []
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 })
    }

    this.setData({ user: app.globalData.user || {} })
    app.request('/rooms').then(rooms => {
      const roomList = Array.isArray(rooms) ? rooms : []
      const roomMap = {}
      roomList.forEach(room => { roomMap[room.room_code] = room })

      const toCell = code => {
        const room = roomMap[code]
        if (!room) {
          return {
            id: '', code, name: '', cls: 'nonpub', tag: '', tagCls: '',
            canReserve: false, isPublic: false
          }
        }

        let cls = 'nonpub'
        let tag = '非公共'
        let tagCls = 'tag-gray'
        if (room.is_public) {
          cls = 'pub'
          tag = STATUS_TEXT[room.public_status] || '状态未知'
          tagCls = 'tag-pub'
        } else if (room.can_reserve) {
          cls = 'res'
          const counselorOnly = room.who_can_reserve === 'counselor'
          tag = counselorOnly ? '辅导员' : '可预约'
          tagCls = counselorOnly ? 'tag-cou' : 'tag-res'
        }

        return {
          id: room.id,
          code: room.room_code,
          name: room.name,
          cls,
          tag,
          tagCls,
          canReserve: room.can_reserve,
          isPublic: room.is_public
        }
      }

      const orderedItems = codes => codes
        .map(code => roomMap[code])
        .filter(Boolean)
        .map(listItem)

      this.setData({
        topRow: TOP_CODES.map(toCell),
        bottomRow: BOTTOM_CODES.map(toCell),
        reservable: orderedItems(RESERVABLE_CODES),
        publics: orderedItems(PUBLIC_CODES)
      })
    }).catch(error => {
      console.error('load rooms failed', error)
      wx.showToast({ title: '空间信息加载失败', icon: 'none' })
    })
  },

  onCell(event) {
    const data = event.currentTarget.dataset
    if ((data.res || data.pub) && data.id) {
      wx.navigateTo({ url: '/pages/room/room?id=' + data.id })
    }
  },

  onRoom(event) {
    const id = event.currentTarget.dataset.id
    if (id) wx.navigateTo({ url: '/pages/room/room?id=' + id })
  },

  goSceneReserve() {
    wx.navigateTo({ url: '/pages/reserve/reserve' })
  },

  doLogout() {
    app.logout()
  }
})
