const app = getApp()
const { toServerUrl } = require('../../config')

const STATUS_TEXT = { free: '空闲', busy: '较满', crowded: '已满' }
const STATUS_COLOR = { free: '#27ae60', busy: '#e67e22', crowded: '#e0556a' }

function todayString() {
  const value = new Date()
  return value.getFullYear() + '-' +
    String(value.getMonth() + 1).padStart(2, '0') + '-' +
    String(value.getDate()).padStart(2, '0')
}

function messageTime(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return String(date.getMonth() + 1) + '月' + String(date.getDate()) + '日 ' +
    String(date.getHours()).padStart(2, '0') + ':' + String(date.getMinutes()).padStart(2, '0')
}

function showError(error, fallback) {
  wx.showToast({ title: (error && error.message) || fallback, icon: 'none' })
}

function labelParts(slot) {
  const parts = String(slot.label || '').split('-')
  return {
    start: parts[0] || '',
    end: parts[1] || parts[0] || ''
  }
}

function buildOccupiedBlocks(slots) {
  const blocks = []
  let current = null

  slots.forEach(slot => {
    if (slot.available) {
      if (current) blocks.push(current)
      current = null
      return
    }

    const labels = labelParts(slot)
    if (current && current.end === slot.slot) {
      current.end = slot.slot + 1
      current.endLabel = labels.end
    } else {
      if (current) blocks.push(current)
      current = {
        start: slot.slot,
        end: slot.slot + 1,
        startLabel: labels.start,
        endLabel: labels.end
      }
    }
  })
  if (current) blocks.push(current)

  return blocks.map(block => ({
    ...block,
    timeLabel: block.startLabel + '-' + block.endLabel
  }))
}

function buildTimelineSegments(slots) {
  const segments = []
  let current = null

  slots.forEach(slot => {
    if (current && current.available === slot.available && current.end === slot.slot) {
      current.end = slot.slot + 1
      return
    }
    if (current) segments.push(current)
    current = { start: slot.slot, end: slot.slot + 1, available: slot.available }
  })
  if (current) segments.push(current)

  return segments.map((segment, index) => {
    const first = index === 0
    const last = index === segments.length - 1
    let borderRadius = '0'
    if (first && last) borderRadius = '8rpx'
    else if (first) borderRadius = '8rpx 0 0 8rpx'
    else if (last) borderRadius = '0 8rpx 8rpx 0'
    return { ...segment, borderRadius }
  })
}

function buildAxisLabels(slots) {
  if (!slots.length) return []
  const labels = []
  const step = Math.max(1, Math.ceil(slots.length / 7))
  for (let index = 0; index < slots.length; index += step) {
    labels.push(labelParts(slots[index]).start)
  }
  const end = labelParts(slots[slots.length - 1]).end
  if (labels[labels.length - 1] !== end) labels.push(end)
  return labels
}

Page({
  data: {
    room: null,
    statusText: '',
    statusColor: '#777777',
    isAdmin: false,
    isCounselor: false,
    canStartReservation: false,
    todayDate: '',
    todayBlocks: [],
    timelineSegments: [],
    axisLabels: [],
    totalSlots: 0,
    slotsLoading: false,
    slotsError: '',
    messages: [],
    messagesLoading: false,
    messagesError: '',
    showPost: false,
    postContent: '',
    postPhoto: '',
    postPhotoDisplay: '',
    photoUploading: false,
    posting: false
  },

  onLoad(options) {
    const roomId = options.id
    this.roomId = roomId
    this.setData({ todayDate: todayString() })

    if (!roomId) {
      wx.showToast({ title: '房间信息异常', icon: 'none' })
      return
    }

    Promise.resolve(app.authReady).catch(() => null).then(() => {
      this.loadMessages()
      return app.request('/rooms/' + roomId)
    }).then(room => {
      const role = app.globalData.user && app.globalData.user.role
      const isAdmin = role === 'admin'
      const isCounselor = role === 'counselor' || isAdmin
      const canStartReservation = Boolean(
        room.can_reserve &&
        (room.who_can_reserve !== 'counselor' || isCounselor)
      )

      this.setData({
        room,
        statusText: STATUS_TEXT[room.public_status] || '状态未知',
        statusColor: STATUS_COLOR[room.public_status] || '#777777',
        isAdmin,
        isCounselor,
        canStartReservation
      })

      if (room.can_reserve) this.loadSlots()
    }).catch(error => {
      console.error('load room failed', error)
      wx.showToast({ title: '房间信息加载失败', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 700)
    })
  },

  loadSlots() {
    this.setData({ slotsLoading: true, slotsError: '' })
    const path = '/rooms/' + this.roomId + '/slots?date=' + encodeURIComponent(this.data.todayDate)
    app.request(path).then(result => {
      const slots = Array.isArray(result.slots) ? result.slots : []
      this.setData({
        todayBlocks: buildOccupiedBlocks(slots),
        timelineSegments: buildTimelineSegments(slots),
        axisLabels: buildAxisLabels(slots),
        totalSlots: slots.length,
        slotsLoading: false
      })
    }).catch(error => {
      console.error('load room slots failed', error)
      this.setData({ slotsLoading: false, slotsError: '今日占用情况加载失败' })
    })
  },

  loadMessages() {
    this.setData({ messagesLoading: true, messagesError: '' })
    app.request('/rooms/' + this.roomId + '/messages').then(result => {
      const messages = (Array.isArray(result) ? result : []).map(message => ({
        ...message,
        createdAtLabel: messageTime(message.created_at),
        photo_urls: (message.photo_urls || []).map(toServerUrl)
      }))
      this.setData({ messages, messagesLoading: false })
    }).catch(error => {
      this.setData({
        messagesLoading: false,
        messagesError: (error && error.message) || '留言加载失败，请点击重试'
      })
    })
  },

  setStatus(event) {
    const status = event.currentTarget.dataset.s
    app.request('/admin/rooms/' + this.data.room.id + '/public-status', {
      method: 'PUT',
      data: { public_status: status }
    }).then(() => {
      this.setData({
        'room.public_status': status,
        statusText: STATUS_TEXT[status],
        statusColor: STATUS_COLOR[status]
      })
      wx.showToast({ title: '已更新', icon: 'success' })
    }).catch(error => {
      console.error('update public status failed', error)
      wx.showToast({ title: '状态更新失败', icon: 'none' })
    })
  },

  goReserve() {
    const roomCode = this.data.room && this.data.room.room_code
    const preferredScene = {
      A103: 'event',
      A105: 'meeting',
      A106: 'meeting',
      B102: 'music'
    }[roomCode] || 'study'
    wx.navigateTo({ url: '/pages/reserve/reserve?scene=' + preferredScene })
  },

  openPost() {
    this.setData({
      showPost: true,
      postContent: '',
      postPhoto: '',
      postPhotoDisplay: ''
    })
  },

  closePost() {
    if (this.data.posting || this.data.photoUploading) return
    this.setData({ showPost: false })
  },

  stopPopup() {},

  onPostContent(event) {
    this.setData({ postContent: event.detail.value })
  },

  choosePhoto() {
    if (this.data.photoUploading || this.data.posting) return
    wx.chooseImage({
      count: 1,
      sizeType: ['compressed'],
      sourceType: ['album', 'camera'],
      success: result => {
        const filePath = result.tempFilePaths[0]
        this.setData({ photoUploading: true })
        wx.showLoading({ title: '上传中...', mask: true })
        app.upload('/rooms/' + this.roomId + '/messages/photo', filePath, { name: 'file' }).then(response => {
          this.setData({
            postPhoto: response.url,
            postPhotoDisplay: toServerUrl(response.url)
          })
        }).catch(error => {
          showError(error, '照片上传失败')
        }).finally(() => {
          wx.hideLoading()
          this.setData({ photoUploading: false })
        })
      },
      fail: error => {
        if (!String(error.errMsg || '').includes('cancel')) showError(error, '选择照片失败')
      }
    })
  },

  removePhoto() {
    if (this.data.posting || this.data.photoUploading) return
    this.setData({ postPhoto: '', postPhotoDisplay: '' })
  },

  submitPost() {
    if (this.data.posting || this.data.photoUploading) return
    const content = this.data.postContent.trim()
    const photoUrls = this.data.postPhoto ? [this.data.postPhoto] : []
    if (!content && !photoUrls.length) {
      wx.showToast({ title: '请输入留言或添加照片', icon: 'none' })
      return
    }
    if (content.length > 500) {
      wx.showToast({ title: '留言不能超过500字', icon: 'none' })
      return
    }

    this.setData({ posting: true })
    app.request('/rooms/' + this.roomId + '/messages', {
      method: 'POST',
      data: { content, photo_urls: photoUrls }
    }).then(() => {
      wx.showToast({ title: '发布成功', icon: 'success' })
      this.setData({
        showPost: false,
        postContent: '',
        postPhoto: '',
        postPhotoDisplay: ''
      })
      return this.loadMessages()
    }).catch(error => {
      showError(error, '留言发布失败')
    }).finally(() => this.setData({ posting: false }))
  },

  previewPhoto(event) {
    const current = event.currentTarget.dataset.url
    const urls = event.currentTarget.dataset.urls || [current]
    wx.previewImage({ current, urls })
  }
})
