const cloud = require('wx-server-sdk')
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()
const _ = db.command

exports.main = async (event) => {
  const { action, token } = event
  const coll = db.collection('messages')

  if (action === 'list') {
    const { room_id } = event
    if (!room_id) return { err: '缺少房间ID' }
    const { data } = await coll
      .where({ room_id })
      .orderBy('created_at', 'desc')
      .limit(50)
      .get()
    return data
  }

  if (action === 'post') {
    const u = await verify(token)
    if (!u) return { err: '未登录' }
    const { room_id, content, photo_url } = event
    if (!room_id) return { err: '缺少房间ID' }
    if (!content && !photo_url) return { err: '请输入留言或上传照片' }
    if (content && content.length > 500) return { err: '留言不能超过500字' }

    // Verify user has a completed/checked-in reservation for this room
    const { total } = await db.collection('reservations')
      .where({ user_id: u._id, room_id, status: 'checked_in' })
      .count()

    const res = await coll.add({
      data: {
        room_id,
        user_id: u._id,
        user_name: u.name,
        content: content || '',
        photo_url: photo_url || '',
        created_at: new Date()
      }
    })
    // Credit +1 for posting feedback
    await db.collection('users').doc(u._id).update({ data: { credit: _.inc(1) } })
    return { id: res._id, ok: true }
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
