const STATUS_LABELS = {
  pending: '待审核', approved: '待使用', rejected: '未通过', cancelled: '已取消',
  in_use: '使用中', cleanup_pending: '待清扫复核', cleanup_rejected: '清扫未通过',
  completed: '已完成', missed: '未签到', active: '待使用', checked_in: '使用中'
}

const SCENE_LABELS = {
  study: '自习', meeting: '开会', event: '大型活动', music: '音乐练习'
}

const DEFAULT_CONFIG = {
  open_hour: 8,
  slot_minutes: 30,
  cancel_deadline_minutes: 30,
  checkin_grace_minutes: 15
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

function normalizePage(payload) {
  if (Array.isArray(payload)) {
    return { items: payload, total: payload.length, limit: payload.length || 1, offset: 0, hasMore: false }
  }
  const items = payload && Array.isArray(payload.items) ? payload.items : []
  const total = Math.max(items.length, Number(payload && payload.total) || 0)
  return {
    items,
    total,
    limit: Number(payload && payload.limit) || items.length || 1,
    offset: Number(payload && payload.offset) || 0,
    hasMore: Boolean(payload && payload.has_more)
  }
}

function formatReservation(item, config = DEFAULT_CONFIG, now = Date.now()) {
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
  const startAt = start.getTime()
  const canCancel = ['pending', 'approved'].includes(status) && now < startAt - Number(config.cancel_deadline_minutes) * 60000
  const canCheckin = status === 'approved' && now >= startAt - 15 * 60000 && now <= startAt + Number(config.checkin_grace_minutes) * 60000
  const canCleanup = ['cleanup_pending', 'cleanup_rejected'].includes(status)
  const canRebook = ['rejected', 'cancelled', 'completed', 'missed'].includes(status)
  const room = item.room || {}

  return Object.assign({}, item, {
    id: item.id,
    status,
    room_code: room.room_code || '?',
    room_name: room.name || '',
    sceneLabel: SCENE_LABELS[item.scene] || '历史预约',
    usageLabel: item.usage_mode === 'shared' ? '共享' : '独占',
    timeLabel: `${minuteLabel(startMinute)}-${minuteLabel(endMinute)}`,
    statLabel: status === 'cleanup_pending' && !item.cleanup ? '待清扫' : (STATUS_LABELS[status] || status),
    statusClass: `s-${status}`,
    people: item.people_count || 1,
    purpose: item.purpose || '',
    reviewNote: item.review_note || '',
    cleanupNote: item.cleanup && item.cleanup.review_note ? item.cleanup.review_note : '',
    cleanupLabel: item.cleanup ? '重新上传清扫照片' : '上传清扫照片',
    canCancel,
    canCheckin,
    canCleanup,
    canRebook
  })
}

function filterReservations(items, filter) {
  if (filter === 'cleanup') return items.filter(item => ['cleanup_pending', 'cleanup_rejected'].includes(item.status))
  if (filter && filter !== 'all') return items.filter(item => item.status === filter)
  return items
}

module.exports = {
  DEFAULT_CONFIG,
  filterReservations,
  formatReservation,
  minuteLabel,
  normalizePage,
  reservationTime
}
