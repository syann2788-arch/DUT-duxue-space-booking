const EXPORT_SCENE_OPTIONS = [
  { value: '', label: '全部场景' },
  { value: 'study', label: '自习' },
  { value: 'meeting', label: '开会' },
  { value: 'event', label: '大型活动' },
  { value: 'music', label: '音乐练习' }
]

const EXPORT_STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待审核' },
  { value: 'approved', label: '待使用' },
  { value: 'rejected', label: '已驳回' },
  { value: 'cancelled', label: '已取消' },
  { value: 'in_use', label: '使用中' },
  { value: 'cleanup_pending', label: '待清扫' },
  { value: 'cleanup_rejected', label: '清扫待重传' },
  { value: 'completed', label: '已完成' },
  { value: 'missed', label: '未签到' }
]

function optionAt(options, index) {
  const numericIndex = Number(index)
  return options[Number.isInteger(numericIndex) && options[numericIndex] ? numericIndex : 0]
}

function optionLabel(options, index) {
  return optionAt(options, index).label
}

function validateExportFilters(filters = {}) {
  const dateFrom = String(filters.dateFrom || '')
  const dateTo = String(filters.dateTo || '')
  if (dateFrom && dateTo && dateFrom > dateTo) return '导出开始日期不能晚于结束日期'
  return ''
}

function buildAdminExportPath(filters = {}) {
  const error = validateExportFilters(filters)
  if (error) throw new Error(error)
  const pairs = [
    ['date_from', filters.dateFrom],
    ['date_to', filters.dateTo],
    ['scene', filters.scene],
    ['status_filter', filters.status]
  ].filter(([, value]) => value !== undefined && value !== null && String(value) !== '')
  const query = pairs.map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`).join('&')
  return '/admin/export.xlsx' + (query ? '?' + query : '')
}

function roomCodePayload(roomId) {
  const value = Number(roomId)
  if (!Number.isInteger(value) || value < 1) throw new Error('房间编号无效')
  return JSON.stringify({ room_id: value })
}

module.exports = {
  EXPORT_SCENE_OPTIONS,
  EXPORT_STATUS_OPTIONS,
  buildAdminExportPath,
  optionAt,
  optionLabel,
  roomCodePayload,
  validateExportFilters
}
