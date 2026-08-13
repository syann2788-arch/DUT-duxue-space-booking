function normalizeLoginState(storage = {}, profile = null) {
  const token = String(storage.token || '')
  if (!token) return { authenticated: false, token: '', user: null }
  if (!profile || !profile.id) return { authenticated: false, token: '', user: null }
  return { authenticated: true, token, user: profile }
}

function consecutiveSelection(slots, selectedSlots, clickedSlot) {
  const available = new Map((slots || []).map(item => [Number(item.slot), item]))
  const clicked = available.get(Number(clickedSlot))
  if (!clicked || !clicked.available) return []
  const current = [...new Set((selectedSlots || []).map(Number))].sort((a, b) => a - b)
  if (current.includes(Number(clickedSlot))) return current.filter(value => value !== Number(clickedSlot))
  const next = [...current, Number(clickedSlot)].sort((a, b) => a - b)
  for (let index = 1; index < next.length; index += 1) {
    if (next[index] !== next[index - 1] + 1) return [Number(clickedSlot)]
  }
  const commonRooms = next.reduce((common, slot) => {
    const item = available.get(slot) || {}
    const ids = new Set((item.available_room_ids || item.availableRoomIds || []).map(Number))
    return common === null ? ids : new Set([...common].filter(id => ids.has(id)))
  }, null)
  return commonRooms && commonRooms.size ? next : [Number(clickedSlot)]
}

function reservationPayload(form = {}) {
  const range = Number.isInteger(Number(form.startSlot)) && Number.isInteger(Number(form.endSlot)) && Number(form.endSlot) > Number(form.startSlot)
    ? Array.from({ length: Number(form.endSlot) - Number(form.startSlot) }, (_, index) => Number(form.startSlot) + index)
    : []
  const selected = [...new Set((form.selectedSlots || range).map(Number))].sort((a, b) => a - b)
  if (!selected.length) throw new Error('请选择预约时段')
  if (!form.campusCardMediaId) throw new Error('请先上传玉兰卡照片')
  return {
    scene: form.scene,
    date: form.date,
    start_slot: selected[0],
    end_slot: selected[selected.length - 1] + 1,
    people_count: Number(form.peopleCount || 1),
    purpose: String(form.purpose || '').trim(),
    campus_card_media_id: form.campusCardMediaId
  }
}

function cleanupPayload(mediaIds) {
  const values = (mediaIds || []).map(String).filter(Boolean)
  if (!values.length) throw new Error('至少上传一张清扫照片')
  if (values.length > 6) throw new Error('清扫照片最多6张')
  return { media_ids: values }
}

function adminReviewPayload(ids, decision, note = '') {
  const reservationIds = [...new Set((ids || []).map(Number).filter(id => Number.isInteger(id) && id > 0))]
  if (!reservationIds.length) throw new Error('请先选择预约')
  if (!['approved', 'rejected'].includes(decision)) throw new Error('审核决定无效')
  return { reservation_ids: reservationIds, decision, note: String(note).trim() }
}

module.exports = { adminReviewPayload, cleanupPayload, consecutiveSelection, normalizeLoginState, reservationPayload }
