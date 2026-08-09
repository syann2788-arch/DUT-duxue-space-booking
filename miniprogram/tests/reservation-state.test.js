const test = require('node:test')
const assert = require('node:assert/strict')

const { buildReservationFlow, buildCurrentTask } = require('../utils/reservation-state')

test('reservation flow exposes the active cleanup stage', () => {
  const flow = buildReservationFlow('cleanup_rejected')
  assert.equal(flow.visible, true)
  assert.deepEqual(flow.items.map(item => item.state), ['done', 'done', 'done', 'current', ''])
})

test('terminal and unknown states do not create a misleading active task', () => {
  assert.equal(buildReservationFlow('cancelled').visible, false)
  assert.equal(buildCurrentTask([{ status: 'completed' }]).action, 'reserve')
})

test('cleanup is prioritized over approved and pending reservations', () => {
  const task = buildCurrentTask([
    { status: 'pending', room_code: 'A101' },
    { status: 'approved', room_code: 'A105', date: '2026-08-10', timeLabel: '08:00-09:00' },
    { status: 'cleanup_pending', room_code: 'B102', cleanup: null }
  ])
  assert.equal(task.filter, 'cleanup')
  assert.match(task.sub, /B102/)
})

test('in-use reservation is prioritized when no cleanup is required', () => {
  const task = buildCurrentTask([
    { status: 'approved', room_code: 'A105', date: '2026-08-10', timeLabel: '09:00-10:00' },
    { status: 'in_use', room_code: 'A101', timeLabel: '08:00-09:00' }
  ])
  assert.equal(task.title, '空间使用中')
  assert.equal(task.filter, 'all')
})
