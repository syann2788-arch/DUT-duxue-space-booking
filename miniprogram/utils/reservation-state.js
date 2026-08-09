const FLOW_LABELS = ['提交', '审核', '使用', '清扫', '完成']
const FLOW_STAGES = {
  pending: 0,
  approved: 1,
  in_use: 2,
  cleanup_pending: 3,
  cleanup_rejected: 3,
  completed: 4
}

function buildReservationFlow(status) {
  const stage = FLOW_STAGES[status]
  return {
    visible: stage !== undefined,
    items: FLOW_LABELS.map((label, index) => ({
      label,
      state: index < stage ? 'done' : (index === stage ? 'current' : '')
    }))
  }
}

function buildCurrentTask(items) {
  const cleanup = items.find(item => item.status === 'cleanup_rejected') ||
    items.find(item => item.status === 'cleanup_pending' && !item.cleanup)
  if (cleanup) {
    return {
      title: '待完成清扫',
      sub: `${cleanup.room_code} · 上传现场照片后可继续预约`,
      filter: 'cleanup',
      action: 'filter'
    }
  }
  const inUse = items.find(item => item.status === 'in_use')
  if (inUse) {
    return {
      title: '空间使用中',
      sub: `${inUse.room_code} · ${inUse.timeLabel}`,
      filter: 'all',
      action: 'filter'
    }
  }
  const approved = items.find(item => item.status === 'approved')
  if (approved) {
    return {
      title: '即将使用',
      sub: `${approved.date} · ${approved.timeLabel}`,
      filter: 'approved',
      action: 'filter'
    }
  }
  const pending = items.find(item => item.status === 'pending')
  if (pending) {
    return {
      title: '等待审核',
      sub: `${pending.room_code} · 结果会在这里更新`,
      filter: 'pending',
      action: 'filter'
    }
  }
  return { title: '暂无待办', sub: '可按需预约书院空间', filter: '', action: 'reserve' }
}

module.exports = { buildReservationFlow, buildCurrentTask }
