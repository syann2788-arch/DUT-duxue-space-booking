const cloud = require('wx-server-sdk')
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()
const _ = db.command
const C = { openHour:8, closeHour:22, slotMinutes:30, maxSlots:8, advanceDays:1, cancelDeadlineMin:30, checkinGraceMin:15, banThreshold:3, banDays:7 }

function slotTime(dateStr, slotIdx) {
  const d = new Date(dateStr + 'T00:00:00+08:00')
  return new Date(d.getTime() + C.openHour * 3600000 + slotIdx * C.slotMinutes * 60000)
}

exports.main = async (event) => {
  const { action, token } = event

  if (action === 'my') {
    const u = await verify(token); if (!u) return { err: '未登录' }
    const { data } = await db.collection('reservations')
      .where({ user_id: u._id }).orderBy('created_at','desc').get()
    if (!data.length) return []
    const roomIds = [...new Set(data.map(r => r.room_id))]
    const rooms = {}
    for (const rid of roomIds) {
      const { data: rd } = await db.collection('rooms').doc(rid).get()
      if (rd) rooms[rid] = rd
    }
    return data.map(r => ({...r, room: rooms[r.room_id] || null }))
  }

  if (action === 'create') {
    const u = await verify(token); if (!u) return { err: '未登录' }
    const { room_id, date, start_slot, end_slot, people_count, reason, notes } = event
    if (!room_id || !date || start_slot == null || end_slot == null) return { err: '参数不全' }
    if (start_slot >= end_slot) return { err: '结束时间必须晚于开始时间' }

    const totalSlots = (C.closeHour - C.openHour) * (60 / C.slotMinutes)
    if (start_slot < 0 || end_slot > totalSlots) return { err: '预约时间在8:00-22:00之间' }
    if (end_slot - start_slot > C.maxSlots) return { err: '单次最多'+C.maxSlots/2+'小时' }
    if (!people_count || people_count < 1) return { err: '请填写使用人数' }
    if (!reason || !reason.trim()) return { err: '请填写申请理由' }

    if (u.banned_until && new Date(u.banned_until) > new Date()) return { err: '您因违约被暂停预约权限' }

    const { data: room } = await db.collection('rooms').doc(room_id).get()
    if (!room || !room.can_reserve) return { err: '该房间不可预约' }
    if (room.who_can_reserve === 'counselor' && u.role !== 'counselor' && u.role !== 'admin') return { err: '仅限辅导员预约' }

    // Date range check — compare ISO date strings to avoid timezone issues
    const beijingNow = new Date(Date.now() + 8 * 3600000)
    const todayStr = beijingNow.toISOString().slice(0, 10)
    const maxStr = new Date(Date.now() + 8 * 3600000 + C.advanceDays * 86400000).toISOString().slice(0, 10)
    if (date > maxStr) return { err: '只能提前'+C.advanceDays+'天预约' }
    if (date < todayStr) return { err: '不能预约过去的日期' }

    // One per day
    const { total: myTodayTotal } = await db.collection('reservations')
      .where({ user_id: u._id, date, status: _.in(['active','checked_in']) }).count()
    if (myTodayTotal > 0) return { err: '当天已有预约，如需修改请先取消' }

    // Overlap check with slot-based comparison
    const { data: conflicts } = await db.collection('reservations')
      .where({ room_id, date, status: _.in(['active','checked_in']),
        start_slot: _.lt(end_slot), end_slot: _.gt(start_slot) }).get()
    if (conflicts.length) return { err: '所选时间段已被他人预约' }

    const res = await db.collection('reservations').add({
      data: { user_id: u._id, room_id, date, start_slot, end_slot, people_count, reason, notes: notes || '',
        status:'active', created_at: new Date(), cancelled_at: null, checked_in_at: null }
    })
    // Best-effort notification — ignore failures
    if (u.openid) {
      try {
        const fmtTime = (slot) => String(Math.floor(8 + slot/2)).padStart(2,'0')+':'+(slot%2===0?'00':'30')
        await cloud.openapi.subscribeMessage.send({
          touser: u.openid,
          templateId: 'JCFEQMxQbFljZcjHgj_Nwg5pwS8HyzOcGMavkuzGEDg',
          data: {
            thing1: { value: room.room_code + ' ' + room.name },
            time2: { value: date + ' ' + fmtTime(start_slot) },
            time3: { value: date + ' ' + fmtTime(end_slot) }
          }
        })
      } catch (e) { /* template not configured yet, silent fail */ }
    }
    return { id: res._id, status:'active' }
  }

  if (action === 'cancel') {
    const u = await verify(token); if (!u) return { err: '未登录' }
    const { reservation_id } = event
    const { data: r } = await db.collection('reservations').doc(reservation_id).get()
    if (!r || r.user_id !== u._id || r.status !== 'active') return { err: '预约不存在或已取消' }
    const start = slotTime(r.date, r.start_slot)
    if (Date.now() > start.getTime() - C.cancelDeadlineMin*60000) return { err: '已超过取消截止时间（开始前'+C.cancelDeadlineMin+'分钟）' }
    await db.collection('reservations').doc(reservation_id).update({ data: { status:'cancelled', cancelled_at: new Date() } })
    return { ok: true }
  }

  if (action === 'checkin') {
    const u = await verify(token); if (!u) return { err: '未登录' }
    const { reservation_id } = event
    const { data: r } = await db.collection('reservations').doc(reservation_id).get()
    if (!r || r.user_id !== u._id || r.status !== 'active') return { err: '预约不存在或状态错误' }
    const start = slotTime(r.date, r.start_slot)
    if (Date.now() > start.getTime() + C.checkinGraceMin*60000) return { err: '已超过签到时限（开始后'+C.checkinGraceMin+'分钟内）' }
    await db.collection('reservations').doc(reservation_id).update({ data: { status:'checked_in', checked_in_at: new Date() } })
    // Credit +1 for on-time checkin
    await db.collection('users').doc(u._id).update({ data: { credit: _.inc(1) } })
    return { ok: true }
  }

  if (action === 'checkMissed') {
    const u = await verify(token); if (!u) return { err: '未登录' }
    const now = new Date()
    const today = new Date(Date.now() + 8 * 3600000).toISOString().slice(0, 10)
    const { data: active } = await db.collection('reservations')
      .where({ status:'active', date: _.lte(today) }).limit(500).get()

    for (const r of active) {
      try {
        const deadline = slotTime(r.date, r.start_slot).getTime() + C.checkinGraceMin*60000
        if (now.getTime() <= deadline) continue

        const { data: user } = await db.collection('users').doc(r.user_id).get()
        if (user && user.banned_until && new Date(user.banned_until) > now) continue

        await db.collection('reservations').doc(r._id).update({ data: { status:'missed' } })

        const { data: existingV } = await db.collection('violations').where({ reservation_id: r._id }).get()
        if (!existingV.length) {
          await db.collection('violations').add({ data: { user_id: r.user_id, reservation_id: r._id, type:'no_show', created_at: now } })
          // Credit -1 for violation
          await db.collection('users').doc(r.user_id).update({ data: { credit: _.inc(-1) } })
        }

        const { total: violCount } = await db.collection('violations').where({ user_id: r.user_id }).count()
        if (violCount >= C.banThreshold) {
          const banUntil = new Date(now.getTime() + C.banDays * 86400000)
          await db.collection('users').doc(r.user_id).update({ data: { banned_until: banUntil } })
          const { data: allViols } = await db.collection('violations').where({ user_id: r.user_id }).get()
          for (const v of allViols) await db.collection('violations').doc(v._id).remove()
        }
      } catch (e) { console.error('checkMissed entry failed', r._id, e) }
    }
    return { ok: true }
  }

  return { err: '未知操作' }
}

async function verify(token) {
  if (!token) return null
  const { data } = await db.collection('users').where({ session_token: token }).get()
  if (!data.length) return null
  const u = data[0]
  if (u.token_expires && u.token_expires < Date.now()) return null
  return u
}
