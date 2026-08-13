const test = require('node:test')
const assert = require('node:assert/strict')

const {
  filterReservations,
  formatReservation,
  minuteLabel,
  normalizePage
} = require('../miniprogram/utils/reservations')
const {
  EXPORT_SCENE_OPTIONS,
  EXPORT_STATUS_OPTIONS,
  buildAdminExportPath,
  optionAt,
  optionLabel,
  roomCodePayload,
  validateExportFilters
} = require('../miniprogram/utils/admin-tools')

test('normalizes both the current paginated contract and legacy list payloads', () => {
  assert.deepEqual(normalizePage([{ id: 1 }]), {
    items: [{ id: 1 }], total: 1, limit: 1, offset: 0, hasMore: false
  })
  assert.deepEqual(normalizePage({
    items: [{ id: 2 }], total: 4, limit: 1, offset: 1, has_more: true
  }), {
    items: [{ id: 2 }], total: 4, limit: 1, offset: 1, hasMore: true
  })
})

test('formats legacy states and computes time-sensitive actions', () => {
  const now = new Date(2026, 7, 13, 9, 20).getTime()
  const item = formatReservation({
    id: 7,
    date: '2026-08-13',
    start_minute: 570,
    end_minute: 630,
    status: 'active',
    scene: 'study',
    usage_mode: 'shared',
    room: { room_code: 'A101', name: '日新阁' }
  }, {
    open_hour: 8, slot_minutes: 30, cancel_deadline_minutes: 30, checkin_grace_minutes: 15
  }, now)

  assert.equal(item.status, 'approved')
  assert.equal(item.timeLabel, '09:30-10:30')
  assert.equal(item.canCheckin, true)
  assert.equal(item.canCancel, false)
  assert.equal(item.room_code, 'A101')
})

test('filters cleanup and status tabs without mutating the source list', () => {
  const source = [
    { id: 1, status: 'pending' },
    { id: 2, status: 'cleanup_pending' },
    { id: 3, status: 'cleanup_rejected' }
  ]
  assert.deepEqual(filterReservations(source, 'cleanup').map(item => item.id), [2, 3])
  assert.deepEqual(filterReservations(source, 'pending').map(item => item.id), [1])
  assert.equal(source.length, 3)
  assert.equal(minuteLabel(485), '08:05')
})

test('builds encoded admin export filters and rejects reversed dates', () => {
  assert.equal(buildAdminExportPath(), '/admin/export.xlsx')
  assert.equal(buildAdminExportPath({
    dateFrom: '2026-08-01',
    dateTo: '2026-08-31',
    scene: 'music',
    status: 'cleanup_pending'
  }), '/admin/export.xlsx?date_from=2026-08-01&date_to=2026-08-31&scene=music&status_filter=cleanup_pending')
  assert.equal(validateExportFilters({ dateFrom: '2026-08-31', dateTo: '2026-08-01' }), '导出开始日期不能晚于结束日期')
  assert.throws(() => buildAdminExportPath({ dateFrom: '2026-08-31', dateTo: '2026-08-01' }))
})

test('keeps export picker options and room scan payload deterministic', () => {
  assert.deepEqual(optionAt(EXPORT_SCENE_OPTIONS, 1), { value: 'study', label: '自习' })
  assert.deepEqual(optionAt(EXPORT_STATUS_OPTIONS, 999), EXPORT_STATUS_OPTIONS[0])
  assert.equal(optionLabel(EXPORT_STATUS_OPTIONS, 999), '全部状态')
  assert.equal(roomCodePayload('12'), '{"room_id":12}')
  assert.throws(() => roomCodePayload(0), /房间编号无效/)
})
