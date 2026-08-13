const ROLE_LABELS = { student: '学生', counselor: '辅导员', admin: '管理员' }
const SCENE_LABELS = { study: '自习', meeting: '开会', event: '大型活动', music: '音乐练习' }
const MODE_LABELS = { shared: '共享', exclusive: '独占' }
const VIOLATION_LABELS = { no_show: '未签到', cleanup_failed: '清扫不合格' }
const RESTRICTION_LABELS = { temporary: '临时限制', timed: '限时限制', permanent: '永久限制' }

function clock(minutes) {
  if (minutes === null || minutes === undefined) return '--:--'
  const value = Number(minutes)
  return String(Math.floor(value / 60)).padStart(2, '0') + ':' + String(value % 60).padStart(2, '0')
}

function dateTime(value) {
  if (!value) return '—'
  return String(value).replace('T', ' ').slice(0, 16)
}

function presentReservation(item = {}, selected = false) {
  return {
    ...item,
    selected,
    sceneLabel: SCENE_LABELS[item.scene] || '历史预约',
    modeLabel: MODE_LABELS[item.usage_mode] || '—',
    timeLabel: clock(item.start_minute) + '-' + clock(item.end_minute),
    cardMediaId: item.campus_card_media_id || ''
  }
}

function presentCleanup(item = {}) {
  return {
    ...presentReservation(item),
    mediaIds: item.cleanup && Array.isArray(item.cleanup.media_ids) ? item.cleanup.media_ids : []
  }
}

function presentUser(user = {}) {
  return {
    ...user,
    initial: String(user.name || '?').slice(0, 1),
    roleLabel: ROLE_LABELS[user.role] || user.role,
    bannedLabel: user.banned_until ? dateTime(user.banned_until) : ''
  }
}

function presentViolation(item = {}) {
  return { ...item, typeLabel: VIOLATION_LABELS[item.type] || item.type, createdLabel: dateTime(item.created_at) }
}

function presentRestriction(item = {}) {
  return {
    ...item,
    levelLabel: RESTRICTION_LABELS[item.level] || item.level,
    startsLabel: dateTime(item.starts_at),
    endsLabel: item.ends_at ? dateTime(item.ends_at) : '永久'
  }
}

module.exports = {
  clock,
  dateTime,
  presentCleanup,
  presentReservation,
  presentRestriction,
  presentUser,
  presentViolation
}
