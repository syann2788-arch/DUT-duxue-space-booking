const PAGE_SIZE = 30

const TABS = [
  { key: 'overview', label: '概览' },
  { key: 'review', label: '预约审核' },
  { key: 'cleanup', label: '清扫复核' },
  { key: 'users', label: '用户' },
  { key: 'rules', label: '分房规则' },
  { key: 'settings', label: '系统配置' }
]

const SETTING_META = [
  ['open_hour', '开放开始（时）', 'number'],
  ['close_hour', '开放结束（时）', 'number'],
  ['slot_minutes', '预约粒度（分钟）', 'number'],
  ['max_minutes_per_day', '每日预约上限（分钟）', 'number'],
  ['advance_days', '可提前预约天数', 'number'],
  ['cancel_deadline_minutes', '取消截止（开始前分钟）', 'number'],
  ['checkin_grace_minutes', '签到宽限（分钟）', 'number'],
  ['auto_approval_time', '每日自动审批时间', 'text'],
  ['reminder_minutes', '开始前提醒（分钟）', 'number'],
  ['temporary_ban_days', '临时限制默认天数', 'number'],
  ['violation_threshold', '自动限制违约阈值', 'number'],
  ['violation_ban_days', '自动限制天数', 'number'],
  ['music_a103_start_hour', 'A103 钢琴开放开始（时）', 'number'],
  ['music_a103_end_hour', 'A103 钢琴开放结束（时）', 'number']
].map(([key, label, inputType]) => ({ key, label, inputType, placeholder: key === 'auto_approval_time' ? 'HH:MM' : '' }))

const RESTRICTION_OPTIONS = [
  { level: 'temporary', label: '临时限制', defaultDays: '1' },
  { level: 'timed', label: '限时限制', defaultDays: '7' },
  { level: 'permanent', label: '永久限制', defaultDays: '' }
]

function loaderForTab(tab) {
  return ({
    overview: 'loadOverview', review: 'loadPendingReservations', cleanup: 'loadCleanupQueue',
    users: 'loadUsers', rules: 'loadRoomRules', settings: 'loadSettings'
  })[tab] || ''
}

function toggleSelection(currentIds, id, limit = 200) {
  const value = Number(id)
  const selected = currentIds.map(Number).filter(Number.isFinite)
  const index = selected.indexOf(value)
  if (index >= 0) selected.splice(index, 1)
  else if (selected.length < limit) selected.push(value)
  return { selected, limitReached: index < 0 && selected.length >= limit && !selected.includes(value) }
}

function buildUserQuery(search, offset = 0, limit = PAGE_SIZE) {
  const query = [`limit=${limit}`, `offset=${Math.max(0, Number(offset) || 0)}`]
  const keyword = String(search || '').trim()
  if (keyword) query.push('search=' + encodeURIComponent(keyword))
  return '/admin/users?' + query.join('&')
}

module.exports = { PAGE_SIZE, RESTRICTION_OPTIONS, SETTING_META, TABS, buildUserQuery, loaderForTab, toggleSelection }
