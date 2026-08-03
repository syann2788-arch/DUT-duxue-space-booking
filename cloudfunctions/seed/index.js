const cloud = require('wx-server-sdk')
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()

const ROOMS = [
  { room_code:'A101', name:'日新阁', description:'创新空间，配备各类科创工具', category:'创新空间', can_reserve:true, is_public:false, who_can_reserve:'all', has_fridge:false, has_instruments:false },
  { room_code:'A102', name:'格物居', description:'图书自习空间，自由使用', category:'图书自习', can_reserve:false, is_public:true, who_can_reserve:'none', has_fridge:false, has_instruments:false },
  { room_code:'A103', name:'致知堂', description:'书院最大空间，适合讲座演出', category:'大剧场', can_reserve:true, is_public:false, who_can_reserve:'all', has_fridge:false, has_instruments:false },
  { room_code:'A104', name:'悠然亭', description:'生活空间，可就餐休息', category:'生活空间', can_reserve:false, is_public:true, who_can_reserve:'none', has_fridge:true, has_instruments:false },
  { room_code:'A105', name:'聚思轩', description:'会议室，适合小组讨论', category:'会议室', can_reserve:true, is_public:false, who_can_reserve:'all', has_fridge:false, has_instruments:false },
  { room_code:'A106', name:'汇心驿', description:'谈心室，用于师生交谈与心灵交流', category:'谈心室', can_reserve:true, is_public:false, who_can_reserve:'counselor', has_fridge:false, has_instruments:false },
  { room_code:'B101', name:'文治堂', description:'院长办公室', category:'办公空间', can_reserve:false, is_public:false, who_can_reserve:'none', has_fridge:false, has_instruments:false },
  { room_code:'B102', name:'韵音阁', description:'器乐练习空间', category:'器乐室', can_reserve:true, is_public:false, who_can_reserve:'all', has_fridge:false, has_instruments:true },
  { room_code:'C101', name:'辅导员宿舍', description:'非公共空间', category:'宿舍', can_reserve:false, is_public:false, who_can_reserve:'none', has_fridge:false, has_instruments:false },
  { room_code:'C102', name:'辅导员宿舍', description:'非公共空间', category:'宿舍', can_reserve:false, is_public:false, who_can_reserve:'none', has_fridge:false, has_instruments:false },
  { room_code:'C103', name:'辅导员宿舍', description:'非公共空间', category:'宿舍', can_reserve:false, is_public:false, who_can_reserve:'none', has_fridge:false, has_instruments:false },
  { room_code:'C104', name:'辅导员宿舍', description:'非公共空间', category:'宿舍', can_reserve:false, is_public:false, who_can_reserve:'none', has_fridge:false, has_instruments:false },
]

exports.main = async () => {
  // Seed rooms
  const roomColl = db.collection('rooms')
  for (const r of ROOMS) {
    const { data } = await roomColl.where({ room_code: r.room_code }).get()
    if (data.length === 0) {
      await roomColl.add({ data: { ...r, public_status: r.is_public ? 'free' : null, created_at: new Date() } })
      console.log('+ room', r.room_code)
    } else {
      console.log('  skip', r.room_code)
    }
  }

  // Seed admin
  const userColl = db.collection('users')
  const { data: admins } = await userColl.where({ student_id: 'admin001' }).get()
  if (admins.length === 0) {
    const crypto = require('crypto')
    const hash = crypto.createHash('sha256').update('admin123').digest('hex')
    await userColl.add({ data: { student_id:'admin001', name:'系统管理员', phone:'', class_name:'笃学书院', password_hash:hash, role:'admin', is_active:true, banned_until:null, created_at:new Date() } })
    console.log('+ admin: admin001 / admin123')
  }

  return { ok: true, rooms: ROOMS.length }
}
