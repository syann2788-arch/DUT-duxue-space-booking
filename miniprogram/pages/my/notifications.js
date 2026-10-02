const app = getApp()
const TYPES = { submitted: '预约提交', review_result: '审核结果', starting_soon: '预约即将开始', restriction: '预约资格与清扫通知' }
const STATUS = { pending: '待发送', sent: '已发送', failed: '未送达，请以本页记录为准' }
Page({
  data: { items: [], busy: false, error: '', hasMore: false },
  onShow() { this.reload() },
  reload() { return this.load(false) },
  more() { return this.load(true) },
  async load(append) {
    if (this.data.busy) return
    this.setData({ busy: true, error: '' })
    try {
      const result = await app.request('/notifications/my?limit=30&offset=' + (append ? this.data.items.length : 0))
      const items = result.items.map(n => ({ id: n.id, title: TYPES[n.type] || n.type, statusLabel: STATUS[n.status] || n.status, reason: n.payload.reason || (n.payload.result === 'approved' ? '审核通过' : ''), room: n.payload.room || '', date: n.payload.date || '', time: n.payload.time || '', endsAt: n.payload.ends_at || '', duration: n.payload.duration || '' }))
      this.setData({ items: append ? this.data.items.concat(items) : items, hasMore: result.has_more })
    } catch (error) { this.setData({ error: error.message || '加载失败' }) }
    finally { this.setData({ busy: false }) }
  }
})