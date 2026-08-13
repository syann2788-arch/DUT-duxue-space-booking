const app = getApp()
const { cleanupPayload } = require('../../utils/booking-flow')
const {
  DEFAULT_CONFIG,
  formatReservation,
  normalizePage
} = require('../../utils/reservations')
const PAGE_SIZE = 30

const FILTER_STATUSES = {
  pending: ['pending'],
  approved: ['approved', 'active'],
  cleanup: ['cleanup_pending', 'cleanup_rejected'],
  completed: ['completed']
}

function pad(value) {
  return String(value).padStart(2, '0')
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
    loadingMore: false,
    loadState: 'idle',
    loadError: '',
    hasMore: false,
    total: 0,
    actionId: null,
    cleanupSubmittingId: null,
    notificationLoading: false,
    bookingConfig: DEFAULT_CONFIG
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

  onReachBottom() {
    this.loadMore()
  },

  retryLoadData() {
    return this.loadData(this._showAttempt)
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
    const raw = this.data.raw.map(item => formatReservation(item, this.data.bookingConfig))
    this.setData({ raw }, () => this.applyFilter())
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
      app.request(this.reservationPath(0)),
      configRequest
    ]).then(([user, reservations, config]) => {
      if (showAttempt !== this._showAttempt || wx.getStorageSync('token') !== tokenAtStart) return
      app.setLogin(tokenAtStart, user)
      const bookingConfig = Object.assign({}, DEFAULT_CONFIG, config || {})
      const page = normalizePage(reservations)
      const raw = page.items.map(item => formatReservation(item, bookingConfig))
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
        counselorCount: this.data.filter === 'all'
          ? raw.filter(item => item.room_code === 'A106').length
          : this.data.counselorCount,
        bookingConfig,
        hasMore: page.hasMore,
        total: page.total,
        loadState: raw.length ? 'success' : 'empty',
        loadError: ''
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
      this.setData({ loadState: this.data.raw.length ? 'success' : 'error', loadError: (error && error.message) || '加载预约记录失败' })
      showError(error, '加载预约记录失败')
    }).finally(() => {
      if (showAttempt === this._showAttempt) this.setData({ loading: false })
    })
  },

  loadMore() {
    if (this.data.loading || this.data.loadingMore || !this.data.hasMore) return Promise.resolve()
    const showAttempt = this._showAttempt
    this.setData({ loadingMore: true, loadError: '' })
    return app.request(this.reservationPath(this.data.raw.length)).then(payload => {
      if (showAttempt !== this._showAttempt) return
      const page = normalizePage(payload)
      const raw = this.data.raw.concat(page.items.map(item => formatReservation(item, this.data.bookingConfig)))
      this.setData({
        raw,
        hasMore: page.hasMore,
        total: page.total,
        counselorCount: this.data.filter === 'all'
          ? raw.filter(item => item.room_code === 'A106').length
          : this.data.counselorCount,
        loadState: raw.length ? 'success' : 'empty'
      }, () => this.applyFilter())
    }).catch(error => {
      if (showAttempt !== this._showAttempt) return
      this.setData({ loadError: (error && error.message) || '更多记录加载失败' })
    }).finally(() => {
      if (showAttempt === this._showAttempt) {
        this.setData({ loadingMore: false }, () => {
          if (!this.data.list.length && this.data.hasMore) this.loadMore()
        })
      }
    })
  },

  setFilter(e) {
    const filter = e.currentTarget.dataset.f
    if (!filter || filter === this.data.filter) return
    this.setData({ filter, raw: [], list: [], total: 0, hasMore: false }, () => this.loadData(this._showAttempt))
  },

  applyFilter() {
    this.setData({ list: this.data.raw })
  },

  reservationPath(offset) {
    const params = [`limit=${PAGE_SIZE}`, `offset=${offset}`]
    ;(FILTER_STATUSES[this.data.filter] || []).forEach(status => params.push(`status_filter=${encodeURIComponent(status)}`))
    return '/reservations/my?' + params.join('&')
  },

  checkin(reservationId) {
    if (this.data.actionId) return Promise.resolve()
    this.setData({ actionId: reservationId })
    return app.request('/reservations/checkin', {
      method: 'POST',
      data: { reservation_id: reservationId }
    }).then(() => {
      wx.showToast({ title: '签到成功', icon: 'success' })
      return this.loadData()
    }).catch(error => {
      showError(error, '签到失败')
    }).finally(() => this.setData({ actionId: null }))
  },

  doCheckin(e) {
    this.checkin(e.currentTarget.dataset.id)
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

  scanCheckin() {
    wx.scanCode({
      onlyFromCamera: true,
      success: result => {
        let roomId = ''
        try {
          const payload = JSON.parse(result.result)
          if (payload && typeof payload === 'object') {
            roomId = payload.room_id != null ? payload.room_id : payload.roomId
          } else {
            roomId = payload
          }
        } catch (error) {
          roomId = String(result.result || '').trim()
        }

        const normalizedRoomId = String(roomId == null ? '' : roomId).trim()
        if (!normalizedRoomId) {
          wx.showToast({ title: '无效的房间码', icon: 'none' })
          return
        }

        const approved = this.data.raw.filter(item =>
          item.status === 'approved' && String(item.room_id) === normalizedRoomId
        )
        if (!approved.length) {
          wx.showToast({ title: '未找到本人该房间的已通过预约', icon: 'none' })
          return
        }
        const match = approved.find(item => item.canCheckin)
        if (!match) {
          wx.showToast({ title: '当前不在签到时间内', icon: 'none' })
          return
        }
        this.checkin(match.id)
      },
      fail: error => {
        if (!String(error.errMsg || '').includes('cancel')) showError(error, '扫码失败')
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
      const mediaIds = []
      for (const filePath of filePaths) {
        const response = await app.upload('/reservations/photos', filePath, { name: 'file' })
        if (!response || !response.media_id) throw new Error('服务器未返回照片凭证')
        mediaIds.push(response.media_id)
      }
      await app.request(`/reservations/${reservationId}/cleanup`, {
        method: 'POST',
        data: cleanupPayload(mediaIds)
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

  goReserve() {
    wx.navigateTo({ url: '/pages/reserve/reserve' })
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
