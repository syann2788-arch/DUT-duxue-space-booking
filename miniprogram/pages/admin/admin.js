const app = getApp()
const { getApiBaseUrl, toServerUrl } = require('../../config')

const TABS = [
  { key: 'overview', label: '概览' },
  { key: 'review', label: '预约审核' },
  { key: 'cleanup', label: '清扫复核' },
  { key: 'users', label: '用户' },
  { key: 'rules', label: '分房规则' },
  { key: 'settings', label: '系统配置' }
]

const ROLE_LABELS = { student: '学生', counselor: '辅导员', admin: '管理员' }
const SCENE_LABELS = { study: '自习', meeting: '开会', event: '大型活动', music: '音乐练习' }
const MODE_LABELS = { shared: '共享', exclusive: '独占' }
const VIOLATION_LABELS = { no_show: '历史未签到（旧版）', cleanup_failed: '清扫不合格' }
const RESTRICTION_LABELS = { temporary: '临时限制', timed: '限时限制', permanent: '永久限制' }
const USAGE_MODES = ['shared', 'exclusive']

const SETTING_META = [
  { key: 'open_hour', label: '开放开始（时）', inputType: 'number' },
  { key: 'close_hour', label: '开放结束（时）', inputType: 'number' },
  { key: 'slot_minutes', label: '预约粒度（分钟）', inputType: 'number' },
  { key: 'max_minutes_per_day', label: '每日预约上限（分钟）', inputType: 'number' },
  { key: 'advance_days', label: '可提前预约天数', inputType: 'number' },
  { key: 'cancel_deadline_minutes', label: '取消截止（开始前分钟）', inputType: 'number' },
  { key: 'auto_approval_time', label: '每日自动审批时间', inputType: 'text', placeholder: 'HH:MM' },
  { key: 'reminder_minutes', label: '开始前提醒（分钟）', inputType: 'number' },
  { key: 'temporary_ban_days', label: '临时限制默认天数', inputType: 'number' },
  { key: 'violation_threshold', label: '自动限制违约阈值', inputType: 'number' },
  { key: 'violation_ban_days', label: '自动限制天数', inputType: 'number' },
  { key: 'music_a103_start_hour', label: 'A103 钢琴开放开始（时）', inputType: 'number' },
  { key: 'music_a103_end_hour', label: 'A103 钢琴开放结束（时）', inputType: 'number' }
]

const RESTRICTION_OPTIONS = [
  { level: 'temporary', label: '临时限制', defaultDays: '1' },
  { level: 'timed', label: '限时限制', defaultDays: '7' },
  { level: 'permanent', label: '永久限制', defaultDays: '' }
]

function clock(minutes) {
  if (minutes === null || minutes === undefined) return '--:--'
  const value = Number(minutes)
  return String(Math.floor(value / 60)).padStart(2, '0') + ':' + String(value % 60).padStart(2, '0')
}

function dateTime(value) {
  if (!value) return '—'
  return String(value).replace('T', ' ').slice(0, 16)
}

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
    tabs: TABS,
    activeTab: 'overview',
    stats: { total_users: 0, pending: 0, cleanup_pending: 0, today: 0 },

    pendingReservations: [],
    selectedPendingIds: [],

    cleanupItems: [],

    userSearch: '',
    users: [],
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
    const loaders = {
      overview: 'loadOverview',
      review: 'loadPendingReservations',
      cleanup: 'loadCleanupQueue',
      users: 'loadUsers',
      rules: 'loadRoomRules',
      settings: 'loadSettings'
    }
    const method = loaders[this.data.activeTab]
    if (method && typeof this[method] === 'function') this[method]()
  },

  async loadOverview() {
    this.setData({ loading: true })
    try {
      const stats = await app.request('/admin/stats') || {}
      this.setData({
        stats: {
          total_users: stats.total_users || 0,
          pending: stats.pending || 0,
          cleanup_pending: stats.cleanup_pending || 0,
          today: stats.today || 0
        }
      })
    } catch (error) {
      toastError(error, '概览加载失败')
    } finally {
      this.setData({ loading: false })
    }
  },

  async loadPendingReservations() {
    this.setData({ loading: true })
    try {
      const data = await app.request('/admin/reservations?status_filter=pending')
      const items = (Array.isArray(data) ? data : []).map(item => ({
        ...item,
        selected: false,
        sceneLabel: SCENE_LABELS[item.scene] || '历史预约',
        modeLabel: MODE_LABELS[item.usage_mode] || '—',
        timeLabel: clock(item.start_minute) + '-' + clock(item.end_minute),
        cardUrl: toServerUrl(item.campus_card_photo_url)
      }))
      this.setData({ pendingReservations: items, selectedPendingIds: [] })
    } catch (error) {
      toastError(error, '待审核预约加载失败')
    } finally {
      this.setData({ loading: false })
    }
  },

  togglePending(event) {
    const id = Number(event.currentTarget.dataset.id)
    const selected = this.data.selectedPendingIds.slice()
    const index = selected.indexOf(id)
    if (index >= 0) selected.splice(index, 1)
    else {
      if (selected.length >= 200) {
        wx.showToast({ title: '每批最多选择200笔', icon: 'none' })
        return
      }
      selected.push(id)
    }
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
        data: {
          reservation_ids: ids.map(Number),
          decision: approved ? 'approved' : 'rejected',
          note: String(modal.content || '').trim()
        }
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
    if (!item || !item.cardUrl) {
      wx.showToast({ title: '没有可查看的玉兰卡照片', icon: 'none' })
      return
    }
    wx.previewImage({
      urls: [item.cardUrl],
      current: item.cardUrl,
      fail: error => toastError(error, '照片预览失败')
    })
  },

  async loadCleanupQueue() {
    this.setData({ loading: true })
    try {
      const data = await app.request('/admin/cleanup')
      const items = (Array.isArray(data) ? data : []).map(item => ({
        ...item,
        sceneLabel: SCENE_LABELS[item.scene] || '历史预约',
        timeLabel: clock(item.start_minute) + '-' + clock(item.end_minute),
        photoUrls: item.cleanup && Array.isArray(item.cleanup.photo_urls)
          ? item.cleanup.photo_urls.map(toServerUrl)
          : []
      }))
      this.setData({ cleanupItems: items })
    } catch (error) {
      toastError(error, '清扫复核队列加载失败')
    } finally {
      this.setData({ loading: false })
    }
  },

  previewCleanupPhoto(event) {
    const item = this.data.cleanupItems[Number(event.currentTarget.dataset.itemIndex)]
    const photoIndex = Number(event.currentTarget.dataset.photoIndex)
    if (!item || !item.photoUrls.length) {
      wx.showToast({ title: '没有可查看的清扫照片', icon: 'none' })
      return
    }
    wx.previewImage({
      urls: item.photoUrls,
      current: item.photoUrls[photoIndex] || item.photoUrls[0],
      fail: error => toastError(error, '照片预览失败')
    })
  },

  async reviewCleanup(event) {
    const cleanupId = Number(event.currentTarget.dataset.id)
    const decision = event.currentTarget.dataset.decision
    const approved = decision === 'approved'
    const modal = await editableModal(approved ? '确认清扫合格' : '清扫复核不通过', approved ? '复核备注（可选）' : '请输入不通过原因')
    if (!modal.confirm) return

    const note = String(modal.content || '').trim() || (approved ? '' : '清扫照片核验不合格，请重新上传')
    let body = { decision: approved ? 'approved' : 'rejected', note, restrict_user: false }
    if (!approved) {
      const action = await actionSheet(['仅退回重传', '退回并临时限制1天', '退回并限时限制7天', '退回并永久限制'])
      if (action === null) return
      if (action === 1) body = { ...body, restrict_user: true, restriction_level: 'temporary', restriction_days: 1 }
      if (action === 2) body = { ...body, restrict_user: true, restriction_level: 'timed', restriction_days: 7 }
      if (action === 3) body = { ...body, restrict_user: true, restriction_level: 'permanent' }
    }

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
    this.loadUsers()
  },

  async loadUsers() {
    this.setData({ loading: true })
    try {
      // FastAPI router names this query parameter "search".
      const keyword = String(this.data.userSearch || '').trim()
      const path = '/admin/users' + (keyword ? '?search=' + encodeURIComponent(keyword) : '')
      const data = await app.request(path)
      const users = (Array.isArray(data) ? data : []).map(user => ({
        ...user,
        initial: String(user.name || '?').slice(0, 1),
        roleLabel: ROLE_LABELS[user.role] || user.role,
        bannedLabel: user.banned_until ? dateTime(user.banned_until) : ''
      }))
      this.setData({ users })
    } catch (error) {
      toastError(error, '用户列表加载失败')
    } finally {
      this.setData({ loading: false })
    }
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
      const violations = (Array.isArray(result[0]) ? result[0] : []).map(item => ({
        ...item,
        typeLabel: VIOLATION_LABELS[item.type] || item.type,
        createdLabel: dateTime(item.created_at)
      }))
      const restrictions = (Array.isArray(result[1]) ? result[1] : []).map(item => ({
        ...item,
        levelLabel: RESTRICTION_LABELS[item.level] || item.level,
        startsLabel: dateTime(item.starts_at),
        endsLabel: item.ends_at ? dateTime(item.ends_at) : '永久',
        createdLabel: dateTime(item.created_at)
      }))
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
    const form = this.data.restrictionForm
    const reason = String(form.reason || '').trim()
    if (reason.length < 2) {
      wx.showToast({ title: '限制原因至少填写2个字', icon: 'none' })
      return
    }
    const body = { level: form.level, reason }
    if (form.level !== 'permanent') {
      const days = Number(form.days)
      if (!Number.isInteger(days) || days < 1 || days > 3650) {
        wx.showToast({ title: '限制天数应为1至3650', icon: 'none' })
        return
      }
      body.days = days
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
    this.setData({ loading: true })
    try {
      const settings = await app.request('/admin/settings')
      const fields = SETTING_META.map(meta => ({
        ...meta,
        placeholder: meta.placeholder || '',
        value: settings[meta.key] === undefined || settings[meta.key] === null ? '' : String(settings[meta.key])
      }))
      this.setData({ settingFields: fields })
    } catch (error) {
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
    const values = {}
    for (const field of this.data.settingFields) {
      if (field.inputType === 'number') {
        if (String(field.value).trim() === '') {
          wx.showToast({ title: field.label + '不能为空', icon: 'none' })
          return
        }
        const value = Number(field.value)
        if (!Number.isInteger(value)) {
          wx.showToast({ title: field.label + '必须为整数', icon: 'none' })
          return
        }
        values[field.key] = value
      } else {
        const value = String(field.value || '').trim()
        if (!value) {
          wx.showToast({ title: field.label + '不能为空', icon: 'none' })
          return
        }
        values[field.key] = value
      }
    }

    wx.showLoading({ title: '保存中...' })
    try {
      await app.request('/admin/settings', { method: 'PUT', data: { values } })
      wx.showToast({ title: '系统配置已保存', icon: 'success' })
      await this.loadSettings()
    } catch (error) {
      toastError(error, '系统配置保存失败')
    } finally {
      wx.hideLoading()
    }
  },

  async loadRoomRules() {
    this.setData({ loading: true })
    try {
      const rooms = await app.request('/rooms')
      const rules = []
      ;(Array.isArray(rooms) ? rooms : []).forEach(room => {
        ;(Array.isArray(room.scene_rules) ? room.scene_rules : []).forEach(rule => {
          rules.push({
            id: rule.id,
            roomId: room.id,
            roomCode: room.room_code,
            roomName: room.name,
            scene: rule.scene,
            sceneLabel: SCENE_LABELS[rule.scene] || rule.scene,
            priority: String(rule.priority),
            capacity: String(rule.capacity),
            usage_mode: rule.usage_mode,
            modeIndex: Math.max(0, USAGE_MODES.indexOf(rule.usage_mode)),
            modeLabel: MODE_LABELS[rule.usage_mode] || rule.usage_mode,
            is_enabled: Boolean(rule.is_enabled)
          })
        })
      })
      rules.sort((left, right) => left.scene.localeCompare(right.scene) || Number(left.priority) - Number(right.priority))
      this.setData({ roomRules: rules })
    } catch (error) {
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
      roomRules: this.data.roomRules.map(rule => rule.id === id ? { ...rule, [field]: value } : rule)
    })
  },

  onRuleModeChange(event) {
    const id = Number(event.currentTarget.dataset.id)
    const modeIndex = Number(event.detail.value)
    this.setData({
      roomRules: this.data.roomRules.map(rule => rule.id === id
        ? {
            ...rule,
            modeIndex,
            usage_mode: USAGE_MODES[modeIndex],
            modeLabel: MODE_LABELS[USAGE_MODES[modeIndex]] || ''
          }
        : rule)
    })
  },

  onRuleEnabledChange(event) {
    const id = Number(event.currentTarget.dataset.id)
    const isEnabled = Boolean(event.detail.value)
    this.setData({
      roomRules: this.data.roomRules.map(rule => rule.id === id ? { ...rule, is_enabled: isEnabled } : rule)
    })
  },

  async saveRoomRule(event) {
    const id = Number(event.currentTarget.dataset.id)
    const rule = this.data.roomRules.find(item => item.id === id)
    if (!rule) {
      wx.showToast({ title: '分房规则不存在', icon: 'none' })
      return
    }
    const priority = Number(rule.priority)
    const capacity = Number(rule.capacity)
    if (!Number.isInteger(priority) || priority < 1 || priority > 999) {
      wx.showToast({ title: '优先级应为1至999', icon: 'none' })
      return
    }
    if (!Number.isInteger(capacity) || capacity < 1 || capacity > 500) {
      wx.showToast({ title: '容量应为1至500', icon: 'none' })
      return
    }
    if (!USAGE_MODES.includes(rule.usage_mode)) {
      wx.showToast({ title: '使用模式无效', icon: 'none' })
      return
    }

    wx.showLoading({ title: '保存中...' })
    try {
      await app.request('/admin/room-rules/' + id, {
        method: 'PUT',
        data: {
          priority,
          capacity,
          usage_mode: rule.usage_mode,
          is_enabled: Boolean(rule.is_enabled)
        }
      })
      wx.showToast({ title: '分房规则已保存', icon: 'success' })
      await this.loadRoomRules()
    } catch (error) {
      toastError(error, '分房规则保存失败')
    } finally {
      wx.hideLoading()
    }
  },

  exportExcel() {
    const token = (app.globalData && app.globalData.token) || wx.getStorageSync('token')
    if (!token) {
      wx.showToast({ title: '登录状态已失效', icon: 'none' })
      return
    }
    wx.showLoading({ title: '生成Excel...' })
    wx.downloadFile({
      url: getApiBaseUrl() + '/admin/export.xlsx',
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
