const cloud = require('wx-server-sdk')
cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })
const db = cloud.database()
const crypto = require('crypto')
const CONFIG = { openHour:8, closeHour:22, slotMinutes:30, maxSlots:8, advanceDays:1, cancelDeadlineMin:30, checkinGraceMin:15, banThreshold:3, banDays:7, tokenDays:7 }

function hash(pw) { return crypto.createHash('sha256').update(pw).digest('hex') }
function token() { return crypto.randomBytes(32).toString('hex') }
function userFields(u) {
  return { id:u._id, student_id:u.student_id, name:u.name, phone:u.phone||'', class_name:u.class_name||'', role:u.role, is_active:u.is_active, banned_until:u.banned_until, credit: u.credit || 0 }
}

exports.main = async (event, context) => {
  const { action, student_id, password, name, phone, class_name } = event
  const users = db.collection('users')
  const wxContext = cloud.getWXContext()
  const openid = wxContext.OPENID

  // Auto-login via WeChat openid — no password needed after first bind
  if (action === 'wechatLogin') {
    if (!openid) return { err: '获取微信信息失败' }
    const { data } = await users.where({ openid, is_active: true }).get()
    if (!data.length) return { err: '未绑定' }
    const u = data[0]
    const tok = token()
    await users.doc(u._id).update({ data: { session_token: tok, token_expires: Date.now() + CONFIG.tokenDays*86400000 } })
    return { token: tok, user: userFields(u) }
  }

  if (action === 'login') {
    if (!student_id || !password) return { err: '请填写学号和密码' }
    const { data } = await users.where({ student_id }).get()
    if (!data.length || data[0].password_hash !== hash(password)) return { err: '学号或密码错误' }
    const u = data[0]
    if (!u.is_active) return { err: '账号已被禁用' }
    // Bind WeChat openid on first login
    if (openid && !u.openid) await users.doc(u._id).update({ data: { openid } })
    const tok = token()
    await users.doc(u._id).update({ data: { session_token: tok, token_expires: Date.now() + CONFIG.tokenDays*86400000 } })
    return { token: tok, user: userFields(u) }
  }

  if (action === 'register') {
    if (!student_id || !name || !phone || !class_name || !password) return { err: '请填写所有字段' }
    if (!/^1[3-9]\d{9}$/.test(phone)) return { err: '手机号格式不正确' }
    if (password.length < 6) return { err: '密码至少6位' }
    if (!/[a-zA-Z]/.test(password) || !/[0-9]/.test(password)) return { err: '密码需同时包含字母和数字' }
    if (!/^\d{4}$/.test(class_name)) return { err: '班级为4位数字（如2502）' }
    const { total } = await users.where({ student_id }).count()
    if (total > 0) return { err: '该学号已注册' }
    const tok = token()
    const res = await users.add({ data: { student_id, name, phone, class_name, password_hash:hash(password), role:'student', is_active:true, banned_until:null, credit:0, openid: openid||'', session_token:tok, token_expires:Date.now()+CONFIG.tokenDays*86400000, created_at:new Date() } })
    return { token: tok, user: { id:res._id, student_id, name, phone, class_name, role:'student', is_active:true, banned_until:null, credit:0 } }
  }

  if (action === 'sendCode') {
    const { phone } = event
    if (!phone) return { err: '请输入手机号' }
    const { data } = await users.where({ phone }).get()
    if (!data.length) return { err: '该手机号未注册' }
    const code = String(Math.floor(100000 + Math.random() * 900000))
    await users.doc(data[0]._id).update({ data: { reset_code: code, reset_expires: Date.now() + 300000 } })

    // Try real SMS; falls back to console log in dev mode
    try {
      await cloud.openapi.cloudbase.sendSms({
        env: cloud.DYNAMIC_CURRENT_ENV,
        phoneNumber: '+86 ' + phone,
        templateId: 'YOUR_SMS_TEMPLATE_ID', // TODO: 在云开发控制台 → SMS 中创建模板后替换
        templateParamSet: [code, '5']
      })
      return { ok: true, msg: '验证码已发送' }
    } catch (e) {
      console.log('=== VERIFICATION CODE [dev fallback] ===', phone, code, '===')
      return { ok: true, msg: '验证码已发送（开发模式，查看云函数日志获取）' }
    }
  }

  if (action === 'resetPassword') {
    const { phone, code, new_password } = event
    if (!phone || !code || !new_password) return { err: '请填写完整信息' }
    if (new_password.length < 6) return { err: '密码至少6位' }
    if (!/[a-zA-Z]/.test(new_password) || !/[0-9]/.test(new_password)) return { err: '密码需同时包含字母和数字' }
    const { data } = await users.where({ phone }).get()
    if (!data.length) return { err: '手机号未注册' }
    const u = data[0]
    if (!u.reset_code || u.reset_code !== code) return { err: '验证码错误' }
    if (!u.reset_expires || u.reset_expires < Date.now()) return { err: '验证码已过期' }
    await users.doc(u._id).update({ data: { password_hash: hash(new_password), reset_code: null, reset_expires: null } })
    return { ok: true }
  }

  if (action === 'me') {
    const u = await verify(event.token)
    if (!u) return { err: '未登录' }
    return userFields(u)
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

exports.verify = verify
exports.CONFIG = CONFIG
