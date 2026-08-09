const app = getApp()
const { buildReservationFlow, buildCurrentTask } = require('../../utils/reservation-state')

const STATUS_LABELS = {
  pending: '待审核',
  approved: '待使用',
  rejected: '未通过',
  cancelled: '已取消',
  in_use: '使用中',
  cleanup_pending: '待清扫复核',
  cleanup_rejected: '清扫未通过',
  completed: '已完成',
  missed: '未签到',
  active: '待使用',
  checked_in: '使用中'
}

const SCENE_LABELS = {
  study: '自习',
  meeting: '开会',
  event: '大型活动',
  music: '音乐练习'
}

const DEFAULT_CONFIG = {
  open_hour: 8,
  slot_minutes: 30,
  cancel_deadline_minutes: 30
}

function pad(value) {
  return String(value).padStart(2, '0')
}

function minuteLabel(value) {
  const minutes = Number(value) || 0
  return `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`
}

function reservationTime(dateValue, minutes) {
  const parts = String(dateValue || '').split('-').map(Number)
  if (parts.length !== 3 || parts.some(Number.isNaN)) return new Date(NaN)
  return new Date(parts[0], parts[1] - 1, parts[2], 0, Number(minutes) || 0, 0, 0)
}

function displayClass(className) {
  const match = String(className || '').match(/\d{4}/)
  return `笃学${match ? match[0] : '----'}`
}

function displayDateTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '禁约中'
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function showError(error, fallback) {
  wx.showToast({ title: (error && error.message) || fallback, icon: 'none' })
}

function loginWithWechat() {
  return new Promise((resolve, reject) => {
    wx.login({ success: resolve, fail: reject })
  })
}

function subscribeMessages(templateIds) {
  return new Promise((resolve, reject) => {
    wx.requestSubscribeMessage({ tmplIds: templateIds, success: resolve, fail: reject })
  })
}

Page({
  data: {
    user: {},
    classLabel: '笃学----',
    isBanned: false,
    banLabel: '预约正常',
    isAdmin: false,
    isC: false,
    filter: 'all',
    tabs: [
      { value: 'all', label: '全部' },
      { value: 'pending', label: '待审核' },
      { value: 'approved', label: '待使用' },
      { value: 'cleanup', label: '待清扫' },
      { value: 'completed', label: '已完成' }
    ],
    list: [],
    raw: [],
    counselorCount: 0,
    loading: false,
    loadState: 'idle',
    loadError: '',
    actionId: null,
    cleanupSubmittingId: null,
    notificationLoading: false,
    bookingConfig: DEFAULT_CONFIG,
    currentTask: {
      title: '暂无待办',
      sub: '可按需预约书院空间',
      filter: '',
      action: 'reserve'
    }
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 })
    }
    const showAttempt = (this._showAttempt || 0) + 1
    this._showAttempt = showAttempt
    Promise.resolve(app.authReady).catch(() => null).then(() => {
      if (showAttempt === this._showAttempt) this.loadData(showAttempt)
    })
    this.startActionTimer()
  },

  onHide() {
    this._showAttempt = (this._showAttempt || 0) + 1
    this.stopActionTimer()
  },

  onUnload() {
    this._showAttempt = (this._showAttempt || 0) + 1
    this.stopActionTimer()
  },

  startActionTimer() {
    this.stopActionTimer()
    this._actionTimer = setInterval(() => this.refreshActionWindows(), 30000)
  },

  stopActionTimer() {
    if (!this._actionTimer) return
    clearInterval(this._actionTimer)
    this._actionTimer = null
  },

  refreshActionWindows() {
    if (!this.data.raw.length) return
    const raw = this.data.raw.map(item => this.formatReservation(item, this.data.bookingConfig))
    this.setData({ raw, currentTask: this.buildCurrentTask(raw) }, () => this.applyFilter())
  },

  loadData(showAttempt = this._showAttempt) {
    const tokenAtStart = wx.getStorageSync('token')
    if (!tokenAtStart) {
      app.logout()
      return Promise.resolve()
    }

    this.setData({ loading: true, loadState: 'loading', loadError: '' })
    const configRequest = app.request('/reservations/config').catch(() => this.data.bookingConfig)
    return Promise.all([
      app.request('/auth/me'),
      app.request('/reservations/my'),
      configRequest
    ]).then(([user, reservations, config]) => {
      if (showAttempt !== this._showAttempt || wx.getStorageSync('token') !== tokenAtStart) return
      app.setLogin(tokenAtStart, user)
      const bookingConfig = Object.assign({}, DEFAULT_CONFIG, config || {})
      const raw = (reservations || []).map(item => this.formatReservation(item, bookingConfig))
      const restrictionEnd = user.restriction_ends_at || user.banned_until
      const bannedUntil = restrictionEnd ? new Date(restrictionEnd) : null
      const legacyBan = Boolean(bannedUntil && !Number.isNaN(bannedUntil.getTime()) && bannedUntil.getTime() > Date.now())
      const isBanned = Boolean(user.booking_restricted || legacyBan)
      const restrictionLabel = user.restriction_ends_at
        ? `禁约至 ${displayDateTime(user.restriction_ends_at)}`
        : (user.booking_restricted ? '永久禁约' : (legacyBan ? `禁约至 ${displayDateTime(user.banned_until)}` : '预约正常'))
      const role = user.role

      this.setData({
        user,
        classLabel: displayClass(user.class_name),
        isBanned,
        banLabel: restrictionLabel,
        isAdmin: role === 'admin',
        isC: role === 'counselor' || role === 'admin',
        raw,
        loadState: raw.length ? 'success' : 'empty',
        currentTask: this.buildCurrentTask(raw),
        counselorCount: raw.filter(item => item.room_code === 'A106').length,
        bookingConfig
      }, () => this.applyFilter())
    }).catch(error => {
      if (showAttempt !== this._showAttempt) return
      const currentToken = wx.getStorageSync('token')
      if (error && error.statusCode === 401) {
        // api.js clears only the token used by this request. If another login
        // already installed a new token, this stale response must do nothing.
        if (!currentToken) app.logout()
        return
      }
      if (currentToken !== tokenAtStart) return
      this.setData({
        loadState: 'error',
        loadError: (error && error.message) || '加载预约记录失败'
      })
      showError(error, '加载预约记录失败')
    }).finally(() => {
      if (showAttempt === this._showAttempt) this.setData({ loading: false })
    })
  },

  retryLoad() {
    this.loadData()
  },

  formatReservation(item, config) {
    // Preserve operability for reservations created by the v1 status model.
    const status = item.status === 'active'
      ? 'approved'
      : (item.status === 'checked_in' ? 'in_use' : item.status)
    const startMinute = item.start_minute != null
      ? Number(item.start_minute)
      : Number(config.open_hour) * 60 + Number(item.start_slot || 0) * Number(config.slot_minutes)
    const endMinute = item.end_minute != null
      ? Number(item.end_minute)
      : Number(config.open_hour) * 60 + Number(item.end_slot || 0) * Number(config.slot_minutes)
    const start = reservationTime(item.date, startMinute)
    const now = Date.now()
    const cancelDeadline = start.getTime() - Number(config.cancel_deadline_minutes) * 60000
    const canCancel = ['pending', 'approved'].includes(status) && now < cancelDeadline
    const canCleanup = ['cleanup_pending', 'cleanup_rejected'].includes(status)
    const canRebook = ['rejected', 'cancelled', 'completed', 'missed'].includes(status)
    const room = item.room || {}
    const flow = buildReservationFlow(status)

    return Object.assign({}, item, {
      id: item.id,
      status,
      room_code: room.room_code || '?',
      room_name: room.name || '',
      sceneLabel: SCENE_LABELS[item.scene] || '历史预约',
      usageLabel: item.usage_mode === 'shared' ? '共享' : '独占',
      timeLabel: `${minuteLabel(startMinute)}-${minuteLabel(endMinute)}`,
      statLabel: status === 'cleanup_pending' && !item.cleanup
        ? '待清扫'
        : (STATUS_LABELS[status] || status),
      statusClass: `s-${status}`,
      people: item.people_count || 1,
      purpose: item.purpose || '',
      reviewNote: item.review_note || '',
      cleanupNote: item.cleanup && item.cleanup.review_note ? item.cleanup.review_note : '',
      cleanupLabel: item.cleanup ? '重新上传清扫照片' : '上传清扫照片',
      canCancel,
      canCleanup,
      canRebook,
      flow: flow.items,
      flowVisible: flow.visible
    })
  },

  buildCurrentTask(items) {
    return buildCurrentTask(items)
  },

  goCurrentTask() {
    const task = this.data.currentTask
    if (task.action === 'filter') {
      this.setData({ filter: task.filter || 'all' }, () => this.applyFilter())
      return
    }
    wx.navigateTo({ url: '/pages/reserve/reserve' })
  },

  setFilter(e) {
    this.setData({ filter: e.currentTarget.dataset.f }, () => this.applyFilter())
  },

  applyFilter() {
    const filter = this.data.filter
    let list = this.data.raw
    if (filter === 'cleanup') {
      list = list.filter(item => ['cleanup_pending', 'cleanup_rejected'].includes(item.status))
    } else if (filter !== 'all') {
      list = list.filter(item => item.status === filter)
    }
    this.setData({ list })
  },

  doCancel(e) {
    const reservationId = e.currentTarget.dataset.id
    if (this.data.actionId) return
    wx.showModal({
      title: '确认取消',
      content: '取消后将释放该时段，确定继续吗？',
      success: result => {
        if (!result.confirm) return
        this.setData({ actionId: reservationId })
        app.request(`/reservations/${reservationId}/cancel`, { method: 'POST' }).then(() => {
          wx.showToast({ title: '已取消', icon: 'success' })
          return this.loadData()
        }).catch(error => {
          showError(error, '取消失败')
        }).finally(() => this.setData({ actionId: null }))
      }
    })
  },

  uploadCleanup(e) {
    const reservationId = e.currentTarget.dataset.id
    if (this.data.cleanupSubmittingId) return
    wx.chooseImage({
      count: 3,
      sizeType: ['compressed'],
      sourceType: ['camera', 'album'],
      success: result => this.submitCleanup(reservationId, result.tempFilePaths.slice(0, 3)),
      fail: error => {
        if (!String(error.errMsg || '').includes('cancel')) showError(error, '选择照片失败')
      }
    })
  },

  async submitCleanup(reservationId, filePaths) {
    if (!filePaths.length) return
    this.setData({ cleanupSubmittingId: reservationId })
    wx.showLoading({ title: '上传中', mask: true })
    try {
      const photoUrls = []
      for (const filePath of filePaths) {
        const response = await app.upload('/reservations/photos', filePath, { name: 'file' })
        photoUrls.push(response.url)
      }
      await app.request(`/reservations/${reservationId}/cleanup`, {
        method: 'POST',
        data: { photo_urls: photoUrls }
      })
      wx.showToast({ title: '已提交复核', icon: 'success' })
      await this.loadData()
    } catch (error) {
      showError(error, '清扫照片提交失败')
    } finally {
      wx.hideLoading()
      this.setData({ cleanupSubmittingId: null })
    }
  },

  rebook(e) {
    const scene = e.currentTarget.dataset.scene || 'study'
    wx.navigateTo({ url: `/pages/reserve/reserve?scene=${encodeURIComponent(scene)}` })
  },

  goAdmin() {
    wx.navigateTo({ url: '/pages/admin/admin' })
  },

  async enableNotifications() {
    if (this.data.notificationLoading) return
    this.setData({ notificationLoading: true })
    try {
      const loginResult = await loginWithWechat()
      if (!loginResult.code) throw new Error('未获取到微信登录凭证')
      await app.request('/auth/wechat/bind', {
        method: 'POST',
        data: { code: loginResult.code }
      })
      const response = await app.request('/notifications/templates')
      const templateIds = Array.from(new Set((response.template_ids || []).filter(Boolean)))
      if (!templateIds.length) {
        wx.showToast({ title: '服务器尚未配置消息模板', icon: 'none' })
        return
      }
      for (let index = 0; index < templateIds.length; index += 3) {
        await subscribeMessages(templateIds.slice(index, index + 3))
      }
      wx.showToast({ title: '通知设置完成', icon: 'success' })
    } catch (error) {
      wx.showToast({ title: (error && error.message) || '未完成通知授权', icon: 'none' })
    } finally {
      this.setData({ notificationLoading: false })
    }
  }
})
