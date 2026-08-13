const test = require('node:test')
const assert = require('node:assert/strict')

const {
  adminReviewPayload,
  cleanupPayload,
  consecutiveSelection,
  normalizeLoginState,
  reservationPayload
} = require('../miniprogram/utils/booking-flow')
const {
  buildUserQuery,
  loaderForTab,
  toggleSelection
} = require('../miniprogram/utils/admin-state')
const {
  cleanupReviewPayload,
  restrictionPayload,
  roomRulePayload,
  settingPayload
} = require('../miniprogram/utils/admin-config')
const {
  presentCleanup,
  presentReservation,
  presentUser
} = require('../miniprogram/utils/admin-presenters')

test('restores authentication only when token and validated profile both exist', () => {
  assert.equal(normalizeLoginState({}, null).authenticated, false)
  assert.equal(normalizeLoginState({ token: 'jwt' }, null).authenticated, false)
  assert.deepEqual(normalizeLoginState({ token: 'jwt' }, { id: 7, role: 'student' }), {
    authenticated: true, token: 'jwt', user: { id: 7, role: 'student' }
  })
})

test('keeps slot selection consecutive and in one common candidate room', () => {
  const slots = [
    { slot: 1, available: true, available_room_ids: [10, 11] },
    { slot: 2, available: true, available_room_ids: [11] },
    { slot: 3, available: true, available_room_ids: [12] },
    { slot: 4, available: false, available_room_ids: [] }
  ]
  assert.deepEqual(consecutiveSelection(slots, [], 1), [1])
  assert.deepEqual(consecutiveSelection(slots, [1], 2), [1, 2])
  assert.deepEqual(consecutiveSelection(slots, [1, 2], 3), [3])
  assert.deepEqual(consecutiveSelection(slots, [1], 4), [])
})

test('builds upload-backed booking and cleanup contracts and rejects invalid input', () => {
  assert.deepEqual(reservationPayload({
    scene: 'study', date: '2026-08-20', selectedSlots: [5, 4], peopleCount: '2',
    purpose: ' 小组讨论 ', campusCardMediaId: 'media-card'
  }), {
    scene: 'study', date: '2026-08-20', start_slot: 4, end_slot: 6,
    people_count: 2, purpose: '小组讨论', campus_card_media_id: 'media-card'
  })
  assert.throws(() => reservationPayload({ selectedSlots: [] }), /请选择预约时段/)
  assert.deepEqual(cleanupPayload(['one', 'two']), { media_ids: ['one', 'two'] })
  assert.throws(() => cleanupPayload([]), /至少上传/)
})

test('builds deterministic admin review contract and feature loaders', () => {
  assert.deepEqual(adminReviewPayload([2, 2, 3], 'approved', ' 通过 '), {
    reservation_ids: [2, 3], decision: 'approved', note: '通过'
  })
  assert.throws(() => adminReviewPayload([], 'approved'), /选择预约/)
  assert.equal(loaderForTab('cleanup'), 'loadCleanupQueue')
  assert.equal(buildUserQuery(' 张 三 ', 30), '/admin/users?limit=30&offset=30&search=%E5%BC%A0%20%E4%B8%89')
})

test('admin feature state and presenters remain isolated and deterministic', () => {
  assert.deepEqual(toggleSelection([], 4).selected, [4])
  assert.deepEqual(toggleSelection([4], 4).selected, [])
  const reservation = presentReservation({
    id: 1, scene: 'study', usage_mode: 'shared', start_minute: 480,
    end_minute: 540, campus_card_media_id: 'card'
  })
  assert.equal(reservation.timeLabel, '08:00-09:00')
  assert.equal(reservation.sceneLabel, '自习')
  assert.deepEqual(presentCleanup({ cleanup: { media_ids: ['a'] } }).mediaIds, ['a'])
  assert.equal(presentUser({ name: '张三', role: 'student' }).initial, '张')
})

test('admin review, restriction, settings and room-rule modules validate independently', () => {
  assert.deepEqual(cleanupReviewPayload('rejected', '', 2), {
    decision: 'rejected', note: '清扫照片核验不合格，请重新上传', restrict_user: true,
    restriction_level: 'timed', restriction_days: 7
  })
  assert.deepEqual(restrictionPayload({ level: 'timed', days: '3', reason: ' 违规 ' }), {
    level: 'timed', days: 3, reason: '违规'
  })
  assert.throws(() => restrictionPayload({ level: 'timed', days: 0, reason: '违规' }), /限制天数/)
  assert.deepEqual(settingPayload([{ key: 'advance_days', label: '提前天数', inputType: 'number', value: '7' }]), {
    values: { advance_days: 7 }
  })
  assert.deepEqual(roomRulePayload({ priority: '1', capacity: '8', usage_mode: 'shared', is_enabled: true }), {
    priority: 1, capacity: 8, usage_mode: 'shared', is_enabled: true
  })
})
