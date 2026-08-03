const cloud = require('wx-server-sdk')
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()
const _ = db.command
const C = { openHour:8, closeHour:22, slotMinutes:30, maxSlots:8 }

function slotLabel(idx) {
  const t = C.openHour * 60 + idx * C.slotMinutes
  const h = Math.floor(t / 60), m = t % 60
  const eh = Math.floor((t + C.slotMinutes) / 60), em = (t + C.slotMinutes) % 60
  return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+'-'+String(eh).padStart(2,'0')+':'+String(em).padStart(2,'0')
}

exports.main = async (event) => {
  const { action, room_id, date } = event

  if (action === 'list') {
    const { data } = await db.collection('rooms').where({ is_active: _.neq(false) }).orderBy('room_code','asc').get()
    return data
  }

  if (action === 'detail') {
    if (!room_id) return { err: '缺少房间ID' }
    const { data } = await db.collection('rooms').doc(room_id).get()
    if (!data) return { err: '房间不存在' }
    return data
  }

  if (action === 'slots') {
    if (!room_id || !date) return { err: '参数不全' }
    const { data: room } = await db.collection('rooms').doc(room_id).get()
    if (!room) return { err: '房间不存在' }

    const { data: existing } = await db.collection('reservations')
      .where({ room_id, date, status: _.in(['active','checked_in']) }).get()

    // Build occupied map: slot index -> { user_name, people, reason }
    const occupied = {}
    if (existing.length) {
      const userIds = [...new Set(existing.map(r => r.user_id))]
      const users = {}
      if (userIds.length) {
        const { data: userList } = await db.collection('users').where({ _id: _.in(userIds) }).get()
        userList.forEach(u => { users[u._id] = u })
      }
      for (const r of existing) {
        const u = users[r.user_id]
        for (let s = r.start_slot; s < r.end_slot; s++) {
          occupied[s] = { user_name: (u && u.name) || '?', user_class: (u && u.class_name) || '', people: r.people_count || 1, reason: r.reason || '' }
        }
      }
    }

    const totalSlots = (C.closeHour - C.openHour) * (60 / C.slotMinutes)
    const slots = []
    for (let i = 0; i < totalSlots; i++) {
      const occ = occupied[i]
      slots.push({
        slot: i,
        label: slotLabel(i),
        available: !occ,
        user_name: occ ? occ.user_name : null,
        user_class: occ ? occ.user_class : null,
        people: occ ? occ.people : null,
        reason: occ ? occ.reason : null
      })
    }
    return { date, slots }
  }

  if (action === 'todaySummary') {
    const d = new Date()
    const today = d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')
    const { data: reservations } = await db.collection('reservations')
      .where({ date: today, status: _.in(['active','checked_in']) })
      .get()
    // Per-room occupied slot count
    const roomOccupied = {}
    reservations.forEach(r => {
      roomOccupied[r.room_id] = (roomOccupied[r.room_id]||0) + (r.end_slot - r.start_slot)
    })
    const totalSlots = (C.closeHour - C.openHour) * (60 / C.slotMinutes)
    const summary = {}
    for (const [rid, slots] of Object.entries(roomOccupied)) {
      summary[rid] = { occupied: slots, total: totalSlots, pct: Math.round(slots/totalSlots*100) }
    }
    return summary
  }

  return { err: '未知操作' }
}
