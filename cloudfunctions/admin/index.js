const cloud = require('wx-server-sdk')
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()
const _ = db.command
const C = { banDays:7 }

exports.main = async (event) => {
  const { action, token } = event
  if (!token) return { err: '未登录' }

  const { data } = await db.collection('users').where({ session_token: token }).get()
  if (!data.length) return { err: '未登录' }
  const admin = data[0]
  if (admin.token_expires && admin.token_expires < Date.now()) return { err: '登录已过期' }
  if (admin.role !== 'admin') return { err: '需要管理员权限' }

  if (action === 'users') {
    const { data } = await db.collection('users').orderBy('student_id','asc').limit(500).get()
    return data.map(x => ({ id:x._id, student_id:x.student_id, name:x.name, phone:x.phone||'', class_name:x.class_name||'', role:x.role, is_active:x.is_active, banned_until:x.banned_until }))
  }

  if (action === 'ban') {
    const { user_id, days } = event
    if (!user_id) return { err: '缺少用户ID' }
    const d = days ?? C.banDays
    if (d <= 0) return { err: '禁约天数必须大于0' }
    const until = new Date(Date.now() + d * 86400000)
    await db.collection('users').doc(user_id).update({ data: { banned_until: until } })
    return { ok: true }
  }

  if (action === 'unban') {
    if (!event.user_id) return { err: '缺少用户ID' }
    await db.collection('users').doc(event.user_id).update({ data: { banned_until: null } })
    return { ok: true }
  }

  if (action === 'publicStatus') {
    const { room_id, public_status } = event
    if (!room_id || !public_status) return { err: '参数不全' }
    if (!['free','busy','crowded'].includes(public_status)) return { err: '状态值无效' }
    await db.collection('rooms').doc(room_id).update({ data: { public_status } })
    return { ok: true }
  }

  if (action === 'reservations') {
    const { date } = event
    const where = date ? { date, status: _.in(['active','checked_in']) } : { status: _.in(['active','checked_in']) }
    const { data: reservations } = await db.collection('reservations').where(where).orderBy('date','desc').limit(200).get()
    return reservations
  }

  if (action === 'stats') {
    const beijingNow = new Date(Date.now() + 8 * 3600000)
    const today = beijingNow.toISOString().slice(0, 10)
    const { total: totalUsers } = await db.collection('users').count()
    const { total: todayActive } = await db.collection('reservations').where({ date:today, status:_.in(['active','checked_in']) }).count()
    const { total: todayMissed } = await db.collection('reservations').where({ date:today, status:'missed' }).count()
    const { total: banned } = await db.collection('users').where({ banned_until: _.gt(new Date()) }).count()

    // Top rooms this month
    const monthStart = beijingNow.toISOString().slice(0, 8) + '01'
    const { data: monthRes } = await db.collection('reservations').where({ date: _.gte(monthStart) }).get()
    const roomCount = {}
    monthRes.forEach(r => { roomCount[r.room_id] = (roomCount[r.room_id]||0)+1 })
    const topRooms = Object.entries(roomCount).sort((a,b)=>b[1]-a[1]).slice(0,5)
    const { data: roomData } = await db.collection('rooms').where({ _id: _.in(topRooms.map(x=>x[0])) }).get()
    const roomMap = {}; roomData.forEach(r => { roomMap[r._id] = r.room_code+' '+r.name })
    const popular = topRooms.map(([id,count]) => ({ name:roomMap[id]||id, count }))

    return { totalUsers, todayActive, todayMissed, banned, popular }
  }

  if (action === 'export') {
    const beijingNow = new Date(Date.now() + 8 * 3600000)
    const monthStr = beijingNow.toISOString().slice(0, 7)
    const { data } = await db.collection('reservations')
      .where({ date: _.gte(monthStr+'-01') }).orderBy('date','asc').limit(1000).get()
    // Fetch related users and rooms
    const userIds = [...new Set(data.map(r => r.user_id))]
    const roomIds = [...new Set(data.map(r => r.room_id))]
    const users = {}, rooms = {}
    if (userIds.length) { const { data: ul } = await db.collection('users').where({ _id: _.in(userIds) }).get(); ul.forEach(u => { users[u._id] = u }) }
    if (roomIds.length) { const { data: rl } = await db.collection('rooms').where({ _id: _.in(roomIds) }).get(); rl.forEach(r => { rooms[r._id] = r }) }

    const L = { active:'待签到', checked_in:'已签到', missed:'违约', cancelled:'已取消' }
    const rows = [['日期','房间','用户姓名','学号','班级','开始时段','结束时段','时长(小时)','使用人数','申请理由','备注','状态']]
    data.forEach(r => {
      const u = users[r.user_id] || {}
      const rm = rooms[r.room_id] || {}
      rows.push([
        r.date, (rm.room_code||'')+' '+rm.name, u.name||'', u.student_id||'', u.class_name||'',
        String(r.start_slot!=null?Math.floor(8+r.start_slot/2)+':'+(r.start_slot%2===0?'00':'30'):''),
        String(r.end_slot!=null?Math.floor(8+r.end_slot/2)+':'+(r.end_slot%2===0?'00':'30'):''),
        String(((r.end_slot||0)-(r.start_slot||0))/2),
        String(r.people_count||1), r.reason||'', r.notes||'', L[r.status]||r.status
      ])
    })
    const csv = '﻿' + rows.map(row => row.map(c => '"'+String(c).replace(/"/g,'""')+'"').join(',')).join('\n')
    return { csv, filename: '书院预约记录_'+monthStr+'.csv' }
  }

  return { err: '未知操作' }
}
