export const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'
export const SERVER_URL = BASE_URL.replace(/\/api\/?$/, '')

function errorMessage(data) {
  if (typeof data?.detail === 'string') return data.detail
  if (Array.isArray(data?.detail)) return data.detail.map(item => item.msg).join('；')
  return '请求失败'
}

export function request(url, options = {}) {
  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync('token')
    const header = { 'Content-Type': 'application/json', ...options.header }
    if (token) header.Authorization = `Bearer ${token}`
    uni.request({
      url: BASE_URL + url,
      method: options.method || 'GET',
      data: options.data,
      header,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) return resolve(res.data)
        const message = errorMessage(res.data)
        uni.showToast({ title: message, icon: 'none', duration: 2500 })
        if (res.statusCode === 401) uni.removeStorageSync('token')
        reject(new Error(message))
      },
      fail(error) {
        uni.showToast({ title: '无法连接服务器', icon: 'none' })
        reject(error)
      },
    })
  })
}

export const login = data => request('/auth/login', { method: 'POST', data })
export const register = data => request('/auth/register', { method: 'POST', data })
export const getMe = () => request('/auth/me')
export const bindWechat = code => request('/auth/wechat/bind', { method: 'POST', data: { code } })

export const getRooms = () => request('/rooms')
export const getRoomDetail = id => request(`/rooms/${id}`)
export const getRoomSlots = (roomId, date) => request(`/rooms/${roomId}/slots?date=${date}`)

export const getBookingConfig = () => request('/reservations/config')
export const createReservation = data => request('/reservations', { method: 'POST', data })
export const cancelReservation = id => request(`/reservations/${id}/cancel`, { method: 'POST' })
export const checkin = reservationId => request('/reservations/checkin', { method: 'POST', data: { reservation_id: reservationId } })
export const getMyReservations = status => request(`/reservations/my${status ? `?status_filter=${status}` : ''}`)
export const submitCleanup = (id, photoUrls) => request(`/reservations/${id}/cleanup`, { method: 'POST', data: { photo_urls: photoUrls } })
export const getNotificationTemplates = () => request('/notifications/templates')

export function uploadCleanupPhoto(filePath) {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${BASE_URL}/reservations/photos`,
      filePath,
      name: 'file',
      header: { Authorization: `Bearer ${uni.getStorageSync('token')}` },
      success(res) {
        const data = JSON.parse(res.data || '{}')
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(data)
        else reject(new Error(errorMessage(data)))
      },
      fail: reject,
    })
  })
}

export function uploadCampusCardPhoto(filePath) {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: `${BASE_URL}/reservations/campus-card-photo`,
      filePath,
      name: 'file',
      header: { Authorization: `Bearer ${uni.getStorageSync('token')}` },
      success(res) {
        const data = JSON.parse(res.data || '{}')
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(data)
        else reject(new Error(errorMessage(data)))
      },
      fail: reject,
    })
  })
}

export const getAdminStats = () => request('/admin/stats')
export const getAllReservations = (date, status, filters = {}) => {
  const query = []
  if (date) query.push(`date=${encodeURIComponent(date)}`)
  if (status) query.push(`status_filter=${encodeURIComponent(status)}`)
  if (filters.date_from) query.push(`date_from=${encodeURIComponent(filters.date_from)}`)
  if (filters.date_to) query.push(`date_to=${encodeURIComponent(filters.date_to)}`)
  if (filters.scene) query.push(`scene=${encodeURIComponent(filters.scene)}`)
  return request(`/admin/reservations${query.length ? `?${query.join('&')}` : ''}`)
}
export const reviewReservations = data => request('/admin/reservations/review', { method: 'POST', data })
export const getCleanupQueue = () => request('/admin/cleanup')
export const reviewCleanup = (id, data) => request(`/admin/cleanup/${id}/review`, { method: 'POST', data })
export const getUsers = search => request(`/admin/users${search ? `?search=${encodeURIComponent(search)}` : ''}`)
export const getViolations = userId => request(`/admin/users/${userId}/violations`)
export const addRestriction = (userId, data) => request(`/admin/users/${userId}/restrictions`, { method: 'POST', data })
export const getRestrictions = userId => request(`/admin/users/${userId}/restrictions`)
export const revokeRestriction = id => request(`/admin/restrictions/${id}`, { method: 'DELETE' })
export const getSettings = () => request('/admin/settings')
export const saveSettings = values => request('/admin/settings', { method: 'PUT', data: { values } })
export const updateRoomRule = (id, data) => request(`/admin/room-rules/${id}`, { method: 'PUT', data })
export const setPublicStatus = (id, publicStatus) => request(`/admin/rooms/${id}/public-status`, { method: 'PUT', data: { public_status: publicStatus } })
export const getCounselors = () => request('/admin/counselors')

export function importCounselors(filePath) {
  return new Promise((resolve, reject) => uni.uploadFile({
    url: `${BASE_URL}/admin/counselors/import`, filePath, name: 'file',
    header: { Authorization: `Bearer ${uni.getStorageSync('token')}` },
    success: res => res.statusCode < 300 ? resolve(JSON.parse(res.data)) : reject(new Error('导入失败')),
    fail: reject,
  }))
}

export function downloadExport(filters = {}) {
  const query = Object.entries(filters).filter(([, value]) => value).map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join('&')
  return uni.downloadFile({
    url: `${BASE_URL}/admin/export.xlsx${query ? `?${query}` : ''}`,
    header: { Authorization: `Bearer ${uni.getStorageSync('token')}` },
    success: res => res.statusCode === 200 && uni.openDocument({ filePath: res.tempFilePath, showMenu: true }),
  })
}
