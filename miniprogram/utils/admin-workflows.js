const { normalizePage } = require('./reservations')
const { presentReservation, dateTime } = require('./admin-presenters')
const { EXPORT_STATUS_OPTIONS, EXPORT_SCENE_OPTIONS } = require('./admin-tools')
const WORK_KINDS = [{ value: 'unuploaded', label: '未上传清扫' }, { value: 'rejected', label: '清扫不合格' }, { value: 'violations', label: '全部违约订单' }, { value: 'unresolved', label: '违规未完结' }]

function orderPath(data, offset = 0) {
  const filters = data.orderFilters || {}
  const status = EXPORT_STATUS_OPTIONS[Number(filters.statusIndex) || 0].value
  const scene = EXPORT_SCENE_OPTIONS[Number(filters.sceneIndex) || 0].value
  let path = `/admin/reservations?limit=30&offset=${offset}`
  for (const [key, value] of [['status_filter', status], ['scene', scene], ['date_from', filters.dateFrom], ['date_to', filters.dateTo]]) {
    if (value) path += '&' + key + '=' + encodeURIComponent(value)
  }
  return path
}

const extraData = {
  resetReason: '', resetAdminPassword: '',
  orderFilters: { statusIndex: 0, sceneIndex: 0, dateFrom: '', dateTo: '' },
  orderStatusOptions: EXPORT_STATUS_OPTIONS, orderSceneOptions: EXPORT_SCENE_OPTIONS,
  allOrders: [], ordersTotal: 0, ordersHasMore: false,
  workKinds: WORK_KINDS, workKindIndex: 0, workItems: [], workTotal: 0, workHasMore: false,
  auditItems: [], auditTotal: 0, auditHasMore: false
}

async function loadPage(page, feature, path, append, presenter) {
  if (page.data.loading) return
  page.setData({ loading: true, loadError: '' })
  try {
    const result = normalizePage(await getApp().request(path))
    const items = result.items.map(presenter)
    const names = { orders: ['allOrders', 'ordersTotal', 'ordersHasMore'], work: ['workItems', 'workTotal', 'workHasMore'], audit: ['auditItems', 'auditTotal', 'auditHasMore'] }[feature]
    page.setData({ [names[0]]: append ? page.data[names[0]].concat(items) : items, [names[1]]: result.total, [names[2]]: result.hasMore })
  } catch (error) {
    page.setData({ loadError: error.message || '加载失败' })
  } finally { page.setData({ loading: false }) }
}

const extraMethods = {
  loadAllOrders(append = false) {
    return loadPage(this, 'orders', orderPath(this.data, append ? this.data.allOrders.length : 0), append, item => ({ ...presentReservation(item), statusLabel: (EXPORT_STATUS_OPTIONS.find(o => o.value === item.status) || {}).label || item.status }))
  },
  loadMoreOrders() { if (this.data.ordersHasMore) return this.loadAllOrders(true) },
  onOrderFilter(e) { this.setData({ ['orderFilters.' + e.currentTarget.dataset.field]: e.detail.value }); this.loadAllOrders() },
  loadWorklist(append = false) {
    const kind = WORK_KINDS[this.data.workKindIndex].value
    return loadPage(this, 'work', `/admin/worklist?kind=${kind}&limit=30&offset=${append ? this.data.workItems.length : 0}`, append, presentReservation)
  },
  onWorkKind(e) { this.setData({ workKindIndex: Number(e.detail.value) }); this.loadWorklist() },
  loadMoreWork() { if (this.data.workHasMore) return this.loadWorklist(true) },
  loadAudit(append = false) {
    return loadPage(this, 'audit', `/admin/audit?limit=30&offset=${append ? this.data.auditItems.length : 0}`, append, item => ({ ...item, timeLabel: dateTime(item.created_at), detailText: JSON.stringify(item.details) }))
  },
  loadMoreAudit() { if (this.data.auditHasMore) return this.loadAudit(true) },
  onRestrictionTime(e) { this.setData({ ['restrictionForm.' + e.currentTarget.dataset.field]: e.detail.value }) },
  clearRestrictionTime() { this.setData({ 'restrictionForm.startDate': '', 'restrictionForm.startTime': '', 'restrictionForm.endDate': '', 'restrictionForm.endTime': '' }) },
  async previewOrderMedia(e) {
    const list = e.currentTarget.dataset.source === 'work' ? this.data.workItems : this.data.allOrders
    const item = list[Number(e.currentTarget.dataset.index)]
    const ids = e.currentTarget.dataset.kind === 'cleanup' ? ((item && item.cleanup && item.cleanup.media_ids) || []) : ((item && item.cardMediaId) ? [item.cardMediaId] : [])
    if (!ids.length) return wx.showToast({ title: '暂无照片或照片已到期', icon: 'none' })
    try {
      const paths = await Promise.all(ids.map(id => getApp().download('/media/' + id)))
      wx.previewImage({ urls: paths, current: paths[0] })
    } catch (error) { wx.showToast({ title: error.message || '照片不可访问', icon: 'none' }) }
  },
  onResetInput(e) { this.setData({ [e.currentTarget.dataset.field]: e.detail.value }) },
  async issuePasswordReset() {
    const user = this.data.selectedUser
    if (!user || this._issuingReset) return
    if (this.data.resetReason.trim().length < 2 || !this.data.resetAdminPassword) return wx.showToast({ title: '请填写核验原因和管理员密码', icon: 'none' })
    const confirmed = await new Promise(resolve => wx.showModal({ title: '确认核验本人身份', content: '仅向已核验的本人签发凭证，确定继续？', success: resolve, fail: () => resolve({ confirm: false }) }))
    if (!confirmed.confirm) return
    this._issuingReset = true
    try {
      const result = await getApp().request('/admin/users/' + user.id + '/password-reset', { method: 'POST', data: { reason: this.data.resetReason.trim(), admin_password: this.data.resetAdminPassword } })
      this.setData({ resetReason: '' })
      wx.setClipboardData({ data: result.credential, success: () => wx.showModal({ title: '一次性重置凭证已复制', content: '30分钟有效，仅交给已核验的本人；用户在忘记密码页面使用。不要发到群聊。', showCancel: false }) })
    } catch (error) { wx.showToast({ title: error.message || '签发失败', icon: 'none' }) }
    finally { this.setData({ resetAdminPassword: '' }); this._issuingReset = false }
  }
}
module.exports = { extraData, extraMethods, orderPath, WORK_KINDS }
