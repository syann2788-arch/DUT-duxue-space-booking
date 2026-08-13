const SCENE_LABELS = { study: '自习', meeting: '开会', event: '大型活动', music: '音乐练习' }
const MODE_LABELS = { shared: '共享', exclusive: '独占' }
const USAGE_MODES = ['shared', 'exclusive']

function overviewData(stats = {}, rooms = []) {
  return {
    stats: {
      total_users: stats.total_users || 0,
      pending: stats.pending || 0,
      cleanup_pending: stats.cleanup_pending || 0,
      today: stats.today || 0
    },
    qrRooms: (Array.isArray(rooms) ? rooms : []).filter(room => room.can_reserve).map(room => ({
      id: room.id, code: room.room_code, name: room.name
    }))
  }
}

function cleanupReviewPayload(decision, note, action = null) {
  const approved = decision === 'approved'
  let payload = {
    decision: approved ? 'approved' : 'rejected',
    note: String(note || '').trim() || (approved ? '' : '清扫照片核验不合格，请重新上传'),
    restrict_user: false
  }
  if (approved || action === null || action === 0) return payload
  if (action === 1) payload = { ...payload, restrict_user: true, restriction_level: 'temporary', restriction_days: 1 }
  if (action === 2) payload = { ...payload, restrict_user: true, restriction_level: 'timed', restriction_days: 7 }
  if (action === 3) payload = { ...payload, restrict_user: true, restriction_level: 'permanent' }
  return payload
}

function restrictionPayload(form = {}) {
  const reason = String(form.reason || '').trim()
  if (reason.length < 2) throw new Error('限制原因至少填写2个字')
  const payload = { level: form.level, reason }
  if (form.level !== 'permanent') {
    const days = Number(form.days)
    if (!Number.isInteger(days) || days < 1 || days > 3650) throw new Error('限制天数应为1至3650')
    payload.days = days
  }
  return payload
}

function settingFields(values, metadata) {
  return metadata.map(meta => ({
    ...meta,
    placeholder: meta.placeholder || '',
    value: values[meta.key] === undefined || values[meta.key] === null ? '' : String(values[meta.key])
  }))
}

function settingPayload(fields) {
  const values = {}
  for (const field of fields) {
    if (String(field.value).trim() === '') throw new Error(field.label + '不能为空')
    if (field.inputType === 'number') {
      const value = Number(field.value)
      if (!Number.isInteger(value)) throw new Error(field.label + '必须为整数')
      values[field.key] = value
    } else {
      values[field.key] = String(field.value).trim()
    }
  }
  return { values }
}

function roomRules(rooms) {
  const rules = []
  ;(Array.isArray(rooms) ? rooms : []).forEach(room => {
    ;(Array.isArray(room.scene_rules) ? room.scene_rules : []).forEach(rule => rules.push({
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
    }))
  })
  return rules.sort((left, right) => left.scene.localeCompare(right.scene) || Number(left.priority) - Number(right.priority))
}

function updateRoomRule(rules, id, change) {
  return rules.map(rule => {
    if (rule.id !== id) return rule
    if (change.modeIndex !== undefined) {
      const modeIndex = Number(change.modeIndex)
      const usageMode = USAGE_MODES[modeIndex]
      return { ...rule, modeIndex, usage_mode: usageMode, modeLabel: MODE_LABELS[usageMode] || '' }
    }
    return { ...rule, ...change }
  })
}

function roomRulePayload(rule) {
  if (!rule) throw new Error('分房规则不存在')
  const priority = Number(rule.priority)
  const capacity = Number(rule.capacity)
  if (!Number.isInteger(priority) || priority < 1 || priority > 999) throw new Error('优先级应为1至999')
  if (!Number.isInteger(capacity) || capacity < 1 || capacity > 500) throw new Error('容量应为1至500')
  if (!USAGE_MODES.includes(rule.usage_mode)) throw new Error('使用模式无效')
  return { priority, capacity, usage_mode: rule.usage_mode, is_enabled: Boolean(rule.is_enabled) }
}

module.exports = {
  cleanupReviewPayload,
  overviewData,
  restrictionPayload,
  roomRulePayload,
  roomRules,
  settingFields,
  settingPayload,
  updateRoomRule
}
