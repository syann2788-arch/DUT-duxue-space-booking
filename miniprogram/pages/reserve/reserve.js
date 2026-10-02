const app = getApp()
const { consecutiveSelection } = require('../../utils/booking-flow')

const SCENES = [
  {
    value: 'study',
    label: '自习',
    icon: '书',
    mode: '共享使用 · 一人一约',
    allocation: '系统依次尝试 A102 → A101 → A105，并按共享容量自动分配。'
  },
  {
    value: 'meeting',
    label: '开会',
    icon: '会',
    mode: '整间独占',
    allocation: '学生依次尝试 A105 → A101 → A102；辅导员账号会优先尝试 A106。'
  },
  {
    value: 'event',
    label: '大型活动',
    icon: '活',
    mode: 'A103 独占',
    allocation: '大型活动仅分配 A103，与该房间的音乐练习时段互斥。'
  },
  {
    value: 'music',
    label: '音乐练习',
    icon: '乐',
    mode: '整间独占',
    allocation: '系统优先分配 B102；A103 钢琴仅在规定开放时段作为备选。'
  }
]

const DEFAULT_CONFIG = {
  open_hour: 8,
  close_hour: 22,
  slot_minutes: 30,
  max_minutes_per_day: 240,
  advance_days: 7,
  cancel_deadline_minutes: 30,
  checkin_grace_minutes: 15
}

Page({
  data: {
    scenes: SCENES,
    scene: 'study',
    currentScene: SCENES[0],
    people: 1,
    peopleInput: '1',
    config: DEFAULT_CONFIG,
    dateOffset: 0,
    dateStr: '',
    dateLabel: '今天',
    slots: [],
    selected: [],
    durationLabel: '',
    maxDurationLabel: '4小时',
    loading: true,
    loadFailed: false
  },

  onLoad(options) {
    this._availabilitySeq = 0
    const initialScene = SCENES.find(item => item.value === (options && options.scene)) || SCENES[0]
    this.setData({
      scene: initialScene.value,
      currentScene: initialScene,
      people: initialScene.value === 'study' ? 1 : this.data.people,
      peopleInput: initialScene.value === 'study' ? '1' : this.data.peopleInput
    })
    this.bootstrap()
  },

  onUnload() {
    this._availabilitySeq += 1
    if (this._peopleTimer) clearTimeout(this._peopleTimer)
  },

  async bootstrap() {
    await Promise.resolve(app.authReady).catch(() => null)
    if (!wx.getStorageSync('token')) {
      app.logout()
      return
    }
    this.setDate(0, false)
    try {
      const remote = await app.request('/reservations/config')
      const config = this.normaliseConfig(remote)
      this.setData({
        config,
        maxDurationLabel: this.formatDuration(config.max_minutes_per_day)
      })
    } catch (err) {
      wx.showToast({ title: err.message || '预约规则加载失败，已使用默认规则', icon: 'none' })
    }
    await this.loadAvailability()
  },

  normaliseConfig(remote) {
    const source = Object.assign({}, DEFAULT_CONFIG, remote || {})
    const numericKeys = [
      'open_hour', 'close_hour', 'slot_minutes', 'max_minutes_per_day',
      'advance_days', 'cancel_deadline_minutes', 'checkin_grace_minutes'
    ]
    numericKeys.forEach(key => {
      const value = Number(source[key])
      source[key] = Number.isFinite(value) ? value : DEFAULT_CONFIG[key]
    })
    source.advance_days = Math.max(0, Math.floor(source.advance_days))
    return source
  },

  fmt(date) {
    return date.getFullYear() + '-' +
      String(date.getMonth() + 1).padStart(2, '0') + '-' +
      String(date.getDate()).padStart(2, '0')
  },

  dateForOffset(offset) {
    const date = new Date()
    date.setHours(0, 0, 0, 0)
    date.setDate(date.getDate() + offset)
    return date
  },

  labelForOffset(offset) {
    if (offset === 0) return '今天'
    if (offset === 1) return '明天'
    return offset + '天后'
  },

  setDate(offset, reload = true) {
    const date = this.dateForOffset(offset)
    this.setData({
      dateOffset: offset,
      dateStr: this.fmt(date),
      dateLabel: this.labelForOffset(offset),
      selected: [],
      durationLabel: ''
    }, () => {
      if (reload) this.loadAvailability()
    })
  },

  changeDate(event) {
    const delta = Number(event.currentTarget.dataset.delta)
    const next = this.data.dateOffset + delta
    const max = this.data.config.advance_days
    if (next < 0) {
      wx.showToast({ title: '不能预约过去的日期', icon: 'none' })
      return
    }
    if (next > max) {
      wx.showToast({ title: '最多可提前' + max + '天预约', icon: 'none' })
      return
    }
    this.setDate(next)
  },

  selectScene(event) {
    const scene = event.currentTarget.dataset.scene
    if (scene === this.data.scene) return
    const currentScene = SCENES.find(item => item.value === scene)
    if (!currentScene) return
    if (this._peopleTimer) clearTimeout(this._peopleTimer)
    const people = scene === 'study' ? 1 : Math.max(1, Number(this.data.people) || 1)
    this.setData({
      scene,
      currentScene,
      people,
      peopleInput: String(people),
      selected: [],
      durationLabel: ''
    }, () => this.loadAvailability())
  },

  onPeopleInput(event) {
    if (this.data.scene === 'study') return
    const peopleInput = String(event.detail.value || '').replace(/\D/g, '').slice(0, 3)
    this.setData({ peopleInput })
    if (this._peopleTimer) clearTimeout(this._peopleTimer)
    this._peopleTimer = setTimeout(() => this.confirmPeople(false), 450)
  },

  onPeopleBlur() {
    if (this._peopleTimer) clearTimeout(this._peopleTimer)
    this.confirmPeople(true)
  },

  confirmPeople(showError) {
    if (this.data.scene === 'study') return true
    const people = Number(this.data.peopleInput)
    if (!Number.isInteger(people) || people < 1 || people > 500) {
      if (showError) wx.showToast({ title: '使用人数须为1至500人', icon: 'none' })
      this.setData({ peopleInput: String(this.data.people) })
      return false
    }
    if (people === this.data.people) return true
    this.setData({ people, selected: [], durationLabel: '' }, () => this.loadAvailability())
    return true
  },

  async loadAvailability() {
    const people = this.data.scene === 'study' ? 1 : Number(this.data.people)
    if (!Number.isInteger(people) || people < 1) return

    const seq = ++this._availabilitySeq
    this.setData({ loading: true, loadFailed: false, selected: [], durationLabel: '' })
    const query = [
      'scene=' + encodeURIComponent(this.data.scene),
      'date=' + encodeURIComponent(this.data.dateStr),
      'people_count=' + encodeURIComponent(people)
    ].join('&')

    try {
      const result = await app.request('/reservations/availability?' + query)
      if (seq !== this._availabilitySeq) return
      const slots = (result.slots || []).map(item => ({
        slot: Number(item.slot),
        label: item.label,
        available: item.available === true,
        availableRoomIds: Array.isArray(item.available_room_ids)
          ? item.available_room_ids.map(Number)
          : (item.available === true ? ['legacy'] : []),
        selected: false
      }))
      this.setData({ slots, loading: false, loadFailed: false })
    } catch (err) {
      if (seq !== this._availabilitySeq) return
      this.setData({ slots: [], loading: false, loadFailed: true })
      wx.showToast({ title: err.message || '可用时段加载失败', icon: 'none' })
    }
  },

  retryAvailability() {
    this.loadAvailability()
  },

  toggleSlot(event) {
    if (this.data.loading) return
    const clicked = Number(event.currentTarget.dataset.slot)
    const clickedItem = this.data.slots.find(item => item.slot === clicked)
    if (!clickedItem || !clickedItem.available) {
      wx.showToast({ title: '该时段暂无可分配空间', icon: 'none' })
      return
    }

    const selected = this.data.selected.slice()
    const selectedIndex = selected.indexOf(clicked)
    if (selectedIndex >= 0) {
      if (selectedIndex !== 0 && selectedIndex !== selected.length - 1) {
        wx.showToast({ title: '只能从已选时段的两端取消', icon: 'none' })
        return
      }
      selected.splice(selectedIndex, 1)
      this.applySelection(selected)
      return
    }

    if (!selected.length) {
      selected.push(clicked)
    } else {
      const min = Math.min(...selected)
      const max = Math.max(...selected)
      const from = clicked < min ? clicked : max + 1
      const to = clicked < min ? min - 1 : clicked
      const slotMap = {}
      this.data.slots.forEach(item => { slotMap[item.slot] = item.available })
      for (let slot = from; slot <= to; slot += 1) {
        if (!slotMap[slot]) {
          wx.showToast({ title: '所选范围包含不可用时段', icon: 'none' })
          return
        }
        selected.push(slot)
      }
    }

    selected.sort((left, right) => left - right)
    const duration = selected.length * this.data.config.slot_minutes
    if (duration > this.data.config.max_minutes_per_day) {
      wx.showToast({ title: '单日预约最多' + this.data.maxDurationLabel, icon: 'none' })
      return
    }
    if (!this.commonAvailableRooms(selected).length) {
      wx.showToast({ title: '整段时间没有同一间可用空间', icon: 'none' })
      return
    }
    this.applySelection(selected)
  },

  commonAvailableRooms(selected) {
    if (!selected.length) return []
    const validated = consecutiveSelection(this.data.slots, selected.slice(0, -1), selected[selected.length - 1])
    if (validated.length !== selected.length || validated.some((slot, index) => slot !== selected[index])) return []
    const selectedSet = new Set(selected)
    const roomSets = this.data.slots.filter(item => selectedSet.has(item.slot)).map(item => item.availableRoomIds || [])
    return roomSets.reduce((common, roomIds) => common.filter(roomId => roomIds.includes(roomId)), roomSets[0] || [])
  },

  applySelection(selected) {
    const selectedSet = new Set(selected)
    const slots = this.data.slots.map(item => Object.assign({}, item, {
      selected: selectedSet.has(item.slot)
    }))
    const minutes = selected.length * this.data.config.slot_minutes
    this.setData({
      slots,
      selected,
      durationLabel: minutes ? this.formatDuration(minutes) : ''
    })
  },

  formatDuration(minutes) {
    const hours = Math.floor(minutes / 60)
    const remainder = minutes % 60
    if (!hours) return remainder + '分钟'
    return hours + '小时' + (remainder ? remainder + '分钟' : '')
  },

  formatTime(slot) {
    const total = this.data.config.open_hour * 60 + slot * this.data.config.slot_minutes
    return String(Math.floor(total / 60)).padStart(2, '0') + ':' + String(total % 60).padStart(2, '0')
  },

  nextStep() {
    if (this.data.scene !== 'study') {
      const people = Number(this.data.peopleInput)
      if (!Number.isInteger(people) || people < 1 || people > 500) {
        wx.showToast({ title: '使用人数须为1至500人', icon: 'none' })
        return
      }
      if (people !== this.data.people) {
        if (this._peopleTimer) clearTimeout(this._peopleTimer)
        this.setData({ people, selected: [], durationLabel: '' }, () => this.loadAvailability())
        wx.showToast({ title: '人数已更新，请重新选择时段', icon: 'none' })
        return
      }
    }
    if (!this.data.selected.length) {
      wx.showToast({ title: '请先选择连续时段', icon: 'none' })
      return
    }
    if (!this.commonAvailableRooms(this.data.selected).length) {
      wx.showToast({ title: '整段时间没有同一间可用空间，请重选', icon: 'none' })
      return
    }

    const startSlot = Math.min(...this.data.selected)
    const endSlot = Math.max(...this.data.selected) + 1
    const timeLabel = this.formatTime(startSlot) + '-' + this.formatTime(endSlot)
    const params = [
      'scene=' + encodeURIComponent(this.data.scene),
      'date=' + encodeURIComponent(this.data.dateStr),
      'startSlot=' + encodeURIComponent(startSlot),
      'endSlot=' + encodeURIComponent(endSlot),
      'timeLabel=' + encodeURIComponent(timeLabel),
      'people=' + encodeURIComponent(this.data.scene === 'study' ? 1 : this.data.people)
    ].join('&')
    wx.navigateTo({ url: '/pages/reserve/form?' + params })
  }
})
