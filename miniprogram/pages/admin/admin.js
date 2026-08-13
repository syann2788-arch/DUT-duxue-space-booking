const app = getApp()
const { adminReviewPayload } = require('../../utils/booking-flow')
const {
  cleanupReviewPayload,
  overviewData,
  restrictionPayload,
  roomRulePayload,
  roomRules,
  settingFields,
  settingPayload,
  updateRoomRule
} = require('../../utils/admin-config')
const { getApiBaseUrl } = require('../../config')
const { normalizePage } = require('../../utils/reservations')
const {
  EXPORT_SCENE_OPTIONS,
  EXPORT_STATUS_OPTIONS,
  buildAdminExportPath,
  optionAt,
  optionLabel,
  roomCodePayload,
  validateExportFilters
} = require('../../utils/admin-tools')
const {
  PAGE_SIZE,
  RESTRICTION_OPTIONS,
  SETTING_META,
  TABS,
  buildUserQuery,
  loaderForTab,
  toggleSelection
} = require('../../utils/admin-state')
const {
  presentCleanup,
  presentReservation,
  presentRestriction,
  presentUser,
  presentViolation
} = require('../../utils/admin-presenters')

function toastError(error, fallback) {
  const message = error && error.message ? error.message : fallback
  wx.showToast({ title: message || fallback, icon: 'none', duration: 3000 })
}

function editableModal(title, placeholder) {
  return new Promise(resolve => {
    wx.showModal({
      title,
      editable: true,
      placeholderText: placeholder || '',
      success: resolve,
      fail: () => resolve({ confirm: false })
    })
  })
}

function actionSheet(itemList) {
  return new Promise(resolve => {
    wx.showActionSheet({
      itemList,
      success: result => resolve(result.tapIndex),
      fail: () => resolve(null)
    })
  })
}

Page({
  data: {
    authorized: false,
    loading: false,
    loadError: '',
    tabs: TABS,
    activeTab: 'overview',
    stats: { total_users: 0, pending: 0, cleanup_pending: 0, today: 0 },
    qrRooms: [],
    exportFilters: { dateFrom: '', dateTo: '', scene: '', status: '' },
    exportSceneOptions: EXPORT_SCENE_OPTIONS,
    exportStatusOptions: EXPORT_STATUS_OPTIONS,
    exportSceneIndex: 0,
    exportStatusIndex: 0,
    exportSceneLabel: optionLabel(EXPORT_SCENE_OPTIONS, 0),
    exportStatusLabel: optionLabel(EXPORT_STATUS_OPTIONS, 0),

    pendingReservations: [],
    selectedPendingIds: [],
    pendingTotal: 0,
    pendingHasMore: false,

    cleanupItems: [],
    cleanupTotal: 0,
    cleanupHasMore: false,

    userSearch: '',
    users: [],
    usersTotal: 0,
    usersHasMore: false,
    selectedUser: null,
    violations: [],
    restrictions: [],
    restrictionOptions: RESTRICTION_OPTIONS,
    restrictionLevelIndex: 0,
    restrictionLevelLabel: RESTRICTION_OPTIONS[0].label,
    restrictionForm: { level: 'temporary', days: '1', reason: '' },

    settingFields: [],

    usageModeLabels: ['共享', '独占'],
    roomRules: []
  },

  onShow() {
    this.authorizeAndLoad()
  },

  authorizeAndLoad() {
    if (this._authorizing) return
    const currentUser = app.globalData.user
    if (currentUser && currentUser.role === 'admin') {
      this._authorized = true
      this.setData({ authorized: true })
      this.loadActiveTab()
      return
    }
    if (currentUser && currentUser.role !== 'admin') {
      this.denyAccess('仅管理员可访问')
      return
    }

    const token = wx.getStorageSync('token')
    if (!token) {
      this.denyAccess('请先以管理员账号登录')
      return
    }

    this._authorizing = true
    app.request('/auth/me').then(user => {
      if (!user || user.role !== 'admin') {
        this.denyAccess('仅管理员可访问')
        return
      }
      app.setLogin(token, user)
      this._authorized = true
      this.setData({ authorized: true })
      this.loadActiveTab()
    }).catch(error => {
      toastError(error, '管理员身份校验失败')
      setTimeout(() => wx.navigateBack(), 700)
    }).finally(() => {
      this._authorizing = false
    })
  },

  denyAccess(message) {
    this._authorized = false
    this.setData({ authorized: false })
    wx.showToast({ title: message, icon: 'none' })
    setTimeout(() => wx.navigateBack(), 700)
  },

  switchTab(event) {
    const key = event.currentTarget.dataset.key
    if (!key || key === this.data.activeTab) return
    this.setData({ activeTab: key })
    this.loadActiveTab()
  },

  loadActiveTab() {
    if (!this._authorized) return
    const method = loaderForTab(this.data.activeTab)
    if (method && typeof this[method] === 'function') this[method]()
  },

  retryActiveTab() {
    this.loadActiveTab()
  },

  async loadOverview() {
    this.setData({ loading: true, loadError: '' })
    try {
      const result = await Promise.all([
        app.request('/admin/stats'),
        app.request('/rooms')
      ])
      this.setData(overviewData(result[0], result[1]))
    } catch (error) {
      this.setData({ loadError: (error && error.message) || '概览加载失败' })
      toastError(error, '概览加载失败')
    } finally {
      this.setData({ loading: false })
    }
  },

  async loadPendingReservations() {
    this.setData({ loading: true, loadError: '' })
    try {
      const page = normalizePage(await app.request(`/admin/reservations?status_filter=pending&limit=${PAGE_SIZE}&offset=0`))
      const items = page.items.map(item => presentReservation(item))
      this.setData({ pendingReservations: items, selectedPendingIds: [], pendingTotal: page.total, pendingHasMore: page.hasMore })
    } catch (error) {
      this.setData({ loadError: (error && error.message) || '待审核预约加载失败' })
      toastError(error, '待审核预约加载失败')
    } finally {
      this.setData({ loading: false })
    }
  },

  async loadMorePending() {
    if (this.data.loading || !this.data.pendingHasMore) return
    this.setData({ loading: true, loadError: '' })
    try {
      const offset = this.data.pendingReservations.length
      const page = normalizePage(await app.request(`/admin/reservations?status_filter=pending&limit=${PAGE_SIZE}&offset=${offset}`))
      const items = page.items.map(item => presentReservation(item))
      this.setData({ pendingReservations: this.data.pendingReservations.concat(items), pendingTotal: page.total, pendingHasMore: page.hasMore })
    } catch (error) {
      this.setData({ loadError: (error && error.message) || '更多待审核预约加载失败' })
    } finally {
      this.setData({ loading: false })
    }
  },

  togglePending(event) {
    const id = Number(event.currentTarget.dataset.id)
    const result = toggleSelection(this.data.selectedPendingIds, id)
    if (result.limitReached) {
      wx.showToast({ title: '每批最多选择200笔', icon: 'none' })
      return
    }
    const selected = result.selected
    this.setData({
      selectedPendingIds: selected,
      pendingReservations: this.data.pendingReservations.map(item => ({
        ...item,
        selected: selected.indexOf(item.id) >= 0
      }))
    })
  },

  toggleAllPending() {
    const allIds = this.data.pendingReservations.map(item => item.id)
    const batchIds = allIds.slice(0, 200)
    const allSelected = batchIds.length > 0 && batchIds.every(id => this.data.selectedPendingIds.includes(id))
    const selectingAll = !allSelected
    if (selectingAll && allIds.length > 200) {
      wx.showToast({ title: '已选择前200笔，请分批审核', icon: 'none' })
    }
    this.setData({
      selectedPendingIds: selectingAll ? batchIds : [],
      pendingReservations: this.data.pendingReservations.map(item => ({
        ...item,
        selected: selectingAll && batchIds.includes(item.id)
      }))
    })
  },

  reviewOne(event) {
    const id = Number(event.currentTarget.dataset.id)
    const decision = event.currentTarget.dataset.decision
    this.submitReservationReview([id], decision)
  },

  reviewSelected(event) {
    const decision = event.currentTarget.dataset.decision
    const ids = this.data.selectedPendingIds
    if (!ids.length) {
      wx.showToast({ title: '请先选择预约', icon: 'none' })
      return
    }
    this.submitReservationReview(ids, decision)
  },

  async submitReservationReview(ids, decision) {
    const approved = decision === 'approved'
    const modal = await editableModal(approved ? '通过预约' : '驳回预约', approved ? '审核备注（可选）' : '请输入驳回原因')
    if (!modal.confirm) return
    wx.showLoading({ title: '处理中...' })
    try {
      const result = await app.request('/admin/reservations/review', {
        method: 'POST',
        data: adminReviewPayload(ids, approved ? 'approved' : 'rejected', modal.content)
      })
      const processed = Number(result.processed) || 0
      const requested = Number(result.requested) || ids.length
      if (!processed) {
        wx.showToast({ title: '这些预约已被其他管理员处理', icon: 'none' })
      } else if (processed < requested) {
        wx.showToast({ title: `已处理${processed}/${requested}笔`, icon: 'none' })
      } else {
        wx.showToast({ title: approved ? `已通过${processed}笔` : `已驳回${processed}笔`, icon: 'success' })
      }
      await this.loadPendingReservations()
    } catch (error) {
      toastError(error, '预约审核失败')
    } finally {
      wx.hideLoading()
    }
  },

  previewCampusCard(event) {
    const item = this.data.pendingReservations[Number(event.currentTarget.dataset.index)]
    if (!item || !item.cardMediaId) {
      wx.showToast({ title: '没有可查看的玉兰卡照片', icon: 'none' })
      return
    }
    wx.showLoading({ title: '安全加载中' })
    app.download('/media/' + item.cardMediaId).then(path => {
      wx.previewImage({ urls: [path], current: path, fail: error => toastError(error, '照片预览失败') })
    }).catch(error => toastError(error, '照片加载失败')).finally(() => wx.hideLoading())
  },

  async loadCleanupQueue() {
    this.setData({ loading: true, loadError: '' })
    try {
      const page = normalizePage(await app.request(`/admin/cleanup?limit=${PAGE_SIZE}&offset=0`))
      const items = page.items.map(presentCleanup)
      this.setData({ cleanupItems: items, cleanupTotal: page.total, cleanupHasMore: page.hasMore })
    } catch (error) {
      this.setData({ loadError: (error && error.message) || '清扫复核队列加载失败' })
      toastError(error, '清扫复核队列加载失败')
    } finally {
      this.setData({ loading: false })
    }
  },

  async loadMoreCleanup() {
    if (this.data.loading || !this.data.cleanupHasMore) return
    this.setData({ loading: true, loadError: '' })
    try {
      const page = normalizePage(await app.request(`/admin/cleanup?limit=${PAGE_SIZE}&offset=${this.data.cleanupItems.length}`))
      const items = page.items.map(presentCleanup)
      this.setData({ cleanupItems: this.data.cleanupItems.concat(items), cleanupTotal: page.total, cleanupHasMore: page.hasMore })
    } catch (error) {
      this.setData({ loadError: (error && error.message) || '更多清扫记录加载失败' })
    } finally {
      this.setData({ loading: false })
    }
  },

  previewCleanupPhoto(event) {
    const item = this.data.cleanupItems[Number(event.currentTarget.dataset.itemIndex)]
    const photoIndex = Number(event.currentTarget.dataset.photoIndex)
    if (!item || !item.mediaIds.length) {
      wx.showToast({ title: '没有可查看的清扫照片', icon: 'none' })
      return
    }
    const mediaId = item.mediaIds[photoIndex] || item.mediaIds[0]
    wx.showLoading({ title: '安全加载中' })
    app.download('/media/' + mediaId).then(path => {
      wx.previewImage({ urls: [path], current: path, fail: error => toastError(error, '照片预览失败') })
    }).catch(error => toastError(error, '照片加载失败')).finally(() => wx.hideLoading())
  },

  async reviewCleanup(event) {
    const cleanupId = Number(event.currentTarget.dataset.id)
    const decision = event.currentTarget.dataset.decision
    const approved = decision === 'approved'
    const modal = await editableModal(approved ? '确认清扫合格' : '清扫复核不通过', approved ? '复核备注（可选）' : '请输入不通过原因')
    if (!modal.confirm) return

    let action = null
    if (!approved) {
      action = await actionSheet(['仅退回重传', '退回并临时限制1天', '退回并限时限制7天', '退回并永久限制'])
      if (action === null) return
    }
    const body = cleanupReviewPayload(decision, modal.content, action)

    wx.showLoading({ title: '处理中...' })
    try {
      await app.request('/admin/cleanup/' + cleanupId + '/review', { method: 'POST', data: body })
      wx.showToast({ title: approved ? '复核已通过' : '已退回处理', icon: 'success' })
      await this.loadCleanupQueue()
    } catch (error) {
      toastError(error, '清扫复核失败')
    } finally {
      wx.hideLoading()
    }
  },

  onUserSearchInput(event) {
    this.setData({ userSearch: event.detail.value })
  },

  searchUsers() {
    this.loadUsers(false)
  },

  async loadUsers(append = false) {
    if (this.data.loading) return
    this.setData({ loading: true, loadError: '' })
    try {
      // FastAPI router names this query parameter "search".
      const offset = append ? this.data.users.length : 0
      const page = normalizePage(await app.request(buildUserQuery(this.data.userSearch, offset)))
      const users = page.items.map(presentUser)
      this.setData({ users: append ? this.data.users.concat(users) : users, usersTotal: page.total, usersHasMore: page.hasMore })
    } catch (error) {
      this.setData({ loadError: (error && error.message) || '用户列表加载失败' })
      toastError(error, '用户列表加载失败')
    } finally {
      this.setData({ loading: false })
    }
  },

  loadMoreUsers() {
    if (this.data.usersHasMore) this.loadUsers(true)
  },

  selectUser(event) {
    const user = this.data.users[Number(event.currentTarget.dataset.index)]
    if (!user) {
      wx.showToast({ title: '用户信息不存在', icon: 'none' })
      return
    }
    this.setData({
      selectedUser: user,
      violations: [],
      restrictions: [],
      restrictionLevelIndex: 0,
      restrictionLevelLabel: RESTRICTION_OPTIONS[0].label,
      restrictionForm: { level: 'temporary', days: '1', reason: '' }
    })
    this.loadUserDetails(user.id)
  },

  refreshSelectedUser() {
    const user = this.data.selectedUser
    if (!user) {
      wx.showToast({ title: '请先选择用户', icon: 'none' })
      return
    }
    this.loadUserDetails(user.id)
  },

  async loadUserDetails(userId) {
    this.setData({ loading: true })
    try {
      const result = await Promise.all([
        app.request('/admin/users/' + userId + '/violations'),
        app.request('/admin/users/' + userId + '/restrictions')
      ])
      const violations = (Array.isArray(result[0]) ? result[0] : []).map(presentViolation)
      const restrictions = (Array.isArray(result[1]) ? result[1] : []).map(presentRestriction)
      this.setData({ violations, restrictions })
    } catch (error) {
      toastError(error, '用户记录加载失败')
    } finally {
      this.setData({ loading: false })
    }
  },

  onRestrictionLevelChange(event) {
    const index = Number(event.detail.value)
    const option = RESTRICTION_OPTIONS[index]
    if (!option) return
    this.setData({
      restrictionLevelIndex: index,
      restrictionLevelLabel: option.label,
      'restrictionForm.level': option.level,
      'restrictionForm.days': option.defaultDays
    })
  },

  onRestrictionDaysInput(event) {
    this.setData({ 'restrictionForm.days': event.detail.value })
  },

  onRestrictionReasonInput(event) {
    this.setData({ 'restrictionForm.reason': event.detail.value })
  },

  async addRestriction() {
    const user = this.data.selectedUser
    if (!user) {
      wx.showToast({ title: '请先选择用户', icon: 'none' })
      return
    }
    let body
    try {
      body = restrictionPayload(this.data.restrictionForm)
    } catch (error) {
      wx.showToast({ title: error.message, icon: 'none' })
      return
    }

    wx.showLoading({ title: '提交中...' })
    try {
      await app.request('/admin/users/' + user.id + '/restrictions', { method: 'POST', data: body })
      wx.showToast({ title: '预约限制已新增', icon: 'success' })
      this.setData({ 'restrictionForm.reason': '' })
      await this.loadUserDetails(user.id)
    } catch (error) {
      toastError(error, '新增限制失败')
    } finally {
      wx.hideLoading()
    }
  },

  async revokeRestriction(event) {
    const restrictionId = Number(event.currentTarget.dataset.id)
    const confirm = await new Promise(resolve => {
      wx.showModal({ title: '解除预约限制', content: '确定解除这条限制吗？', success: resolve, fail: () => resolve({ confirm: false }) })
    })
    if (!confirm.confirm) return
    wx.showLoading({ title: '处理中...' })
    try {
      await app.request('/admin/restrictions/' + restrictionId, { method: 'DELETE' })
      wx.showToast({ title: '限制已解除', icon: 'success' })
      await this.loadUserDetails(this.data.selectedUser.id)
    } catch (error) {
      toastError(error, '解除限制失败')
    } finally {
      wx.hideLoading()
    }
  },

  async loadSettings() {
    this.setData({ loading: true, loadError: '' })
    try {
      this.setData({ settingFields: settingFields(await app.request('/admin/settings'), SETTING_META) })
    } catch (error) {
      this.setData({ loadError: (error && error.message) || '系统配置加载失败' })
      toastError(error, '系统配置加载失败')
    } finally {
      this.setData({ loading: false })
    }
  },

  onSettingInput(event) {
    const key = event.currentTarget.dataset.key
    const value = event.detail.value
    this.setData({
      settingFields: this.data.settingFields.map(field => field.key === key ? { ...field, value } : field)
    })
  },

  async saveSettings() {
    let data
    try {
      data = settingPayload(this.data.settingFields)
    } catch (error) {
      wx.showToast({ title: error.message, icon: 'none' })
      return
    }

    wx.showLoading({ title: '保存中...' })
    try {
      await app.request('/admin/settings', { method: 'PUT', data })
      wx.showToast({ title: '系统配置已保存', icon: 'success' })
      await this.loadSettings()
    } catch (error) {
      toastError(error, '系统配置保存失败')
    } finally {
      wx.hideLoading()
    }
  },

  async loadRoomRules() {
    this.setData({ loading: true, loadError: '' })
    try {
      this.setData({ roomRules: roomRules(await app.request('/rooms')) })
    } catch (error) {
      this.setData({ loadError: (error && error.message) || '分房规则加载失败' })
      toastError(error, '分房规则加载失败')
    } finally {
      this.setData({ loading: false })
    }
  },

  onRuleInput(event) {
    const id = Number(event.currentTarget.dataset.id)
    const field = event.currentTarget.dataset.field
    const value = event.detail.value
    this.setData({
      roomRules: updateRoomRule(this.data.roomRules, id, { [field]: value })
    })
  },

  onRuleModeChange(event) {
    const id = Number(event.currentTarget.dataset.id)
    const modeIndex = Number(event.detail.value)
    this.setData({
      roomRules: updateRoomRule(this.data.roomRules, id, { modeIndex })
    })
  },

  onRuleEnabledChange(event) {
    const id = Number(event.currentTarget.dataset.id)
    const isEnabled = Boolean(event.detail.value)
    this.setData({
      roomRules: updateRoomRule(this.data.roomRules, id, { is_enabled: isEnabled })
    })
  },

  async saveRoomRule(event) {
    const id = Number(event.currentTarget.dataset.id)
    let data
    try {
      data = roomRulePayload(this.data.roomRules.find(item => item.id === id))
    } catch (error) {
      wx.showToast({ title: error.message, icon: 'none' })
      return
    }

    wx.showLoading({ title: '保存中...' })
    try {
      await app.request('/admin/room-rules/' + id, {
        method: 'PUT',
        data
      })
      wx.showToast({ title: '分房规则已保存', icon: 'success' })
      await this.loadRoomRules()
    } catch (error) {
      toastError(error, '分房规则保存失败')
    } finally {
      wx.hideLoading()
    }
  },

  copyRoomCode(event) {
    const roomId = Number(event.currentTarget.dataset.id)
    wx.setClipboardData({
      data: roomCodePayload(roomId),
      success: () => wx.showToast({ title: '签到码内容已复制', icon: 'success' }),
      fail: error => toastError(error, '签到码复制失败')
    })
  },

  previewRoomCode(event) {
    const roomId = Number(event.currentTarget.dataset.id)
    const token = (app.globalData && app.globalData.token) || wx.getStorageSync('token')
    if (!token || !Number.isInteger(roomId)) {
      wx.showToast({ title: '登录状态已失效', icon: 'none' })
      return
    }
    wx.showLoading({ title: '生成签到码...' })
    wx.downloadFile({
      url: getApiBaseUrl() + '/admin/rooms/' + roomId + '/checkin-qr',
      header: { Authorization: 'Bearer ' + token },
      timeout: 30000,
      success: result => {
        if (result.statusCode !== 200) {
          wx.showToast({ title: '签到码生成失败（' + result.statusCode + '）', icon: 'none' })
          return
        }
        wx.previewImage({
          current: result.tempFilePath,
          urls: [result.tempFilePath],
          showmenu: true,
          fail: error => toastError(error, '签到码预览失败')
        })
      },
      fail: error => toastError(error, '签到码下载失败'),
      complete: () => wx.hideLoading()
    })
  },

  onExportDateFromChange(event) {
    this.setData({ 'exportFilters.dateFrom': event.detail.value || '' })
  },

  onExportDateToChange(event) {
    this.setData({ 'exportFilters.dateTo': event.detail.value || '' })
  },

  onExportSceneChange(event) {
    const index = Number(event.detail.value) || 0
    this.setData({
      exportSceneIndex: index,
      exportSceneLabel: optionLabel(EXPORT_SCENE_OPTIONS, index),
      'exportFilters.scene': optionAt(EXPORT_SCENE_OPTIONS, index).value
    })
  },

  onExportStatusChange(event) {
    const index = Number(event.detail.value) || 0
    this.setData({
      exportStatusIndex: index,
      exportStatusLabel: optionLabel(EXPORT_STATUS_OPTIONS, index),
      'exportFilters.status': optionAt(EXPORT_STATUS_OPTIONS, index).value
    })
  },

  clearExportFilters() {
    this.setData({
      exportFilters: { dateFrom: '', dateTo: '', scene: '', status: '' },
      exportSceneIndex: 0,
      exportStatusIndex: 0,
      exportSceneLabel: optionLabel(EXPORT_SCENE_OPTIONS, 0),
      exportStatusLabel: optionLabel(EXPORT_STATUS_OPTIONS, 0)
    })
  },

  exportExcel() {
    const token = (app.globalData && app.globalData.token) || wx.getStorageSync('token')
    if (!token) {
      wx.showToast({ title: '登录状态已失效', icon: 'none' })
      return
    }
    const validationError = validateExportFilters(this.data.exportFilters)
    if (validationError) {
      wx.showToast({ title: validationError, icon: 'none' })
      return
    }
    wx.showLoading({ title: '生成Excel...' })
    wx.downloadFile({
      url: getApiBaseUrl() + buildAdminExportPath(this.data.exportFilters),
      header: { Authorization: 'Bearer ' + token },
      timeout: 30000,
      success: result => {
        if (result.statusCode !== 200) {
          wx.showToast({ title: 'Excel导出失败（' + result.statusCode + '）', icon: 'none' })
          return
        }
        wx.openDocument({
          filePath: result.tempFilePath,
          fileType: 'xlsx',
          showMenu: true,
          fail: error => toastError(error, 'Excel打开失败')
        })
      },
      fail: error => toastError(error, 'Excel下载失败'),
      complete: () => wx.hideLoading()
    })
  },

  importCounselors() {
    wx.chooseMessageFile({
      count: 1,
      type: 'file',
      extension: ['csv'],
      success: result => {
        const file = result.tempFiles && result.tempFiles[0]
        if (!file || !file.path) {
          wx.showToast({ title: '未选择CSV文件', icon: 'none' })
          return
        }
        this.uploadCounselorCsv(file)
      },
      fail: error => {
        if (!String(error.errMsg || '').includes('cancel')) toastError(error, '选择CSV失败')
      }
    })
  },

  async uploadCounselorCsv(file) {
    wx.showLoading({ title: '正在导入...' })
    try {
      const result = await app.upload('/admin/counselors/import', file.path, { name: 'file' })
      const count = Number(result.imported_count) || 0
      const accounts = Array.isArray(result.accounts) ? result.accounts : []
      if (accounts.length) {
        const accountText = accounts.map(item => `${item.name}：${item.login_id} / ${item.password}`).join('\n')
        wx.setClipboardData({
          data: accountText,
          success: () => wx.showModal({
            title: `已导入${count}名辅导员`,
            content: '新账号和初始密码已复制到剪贴板，请立即保存到学校的受控文档并通知本人修改。',
            showCancel: false
          })
        })
      } else {
        wx.showToast({ title: `已导入${count}条`, icon: count ? 'success' : 'none' })
      }
      await this.loadUsers()
    } catch (error) {
      toastError(error, '辅导员CSV导入失败')
    } finally {
      wx.hideLoading()
    }
  }
})
