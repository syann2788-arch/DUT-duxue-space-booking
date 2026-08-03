<template>
  <view class="page">
    <view class="profile" v-if="store.user">
      <view class="avatar">{{ store.user.name.slice(0, 1) }}</view>
      <view class="profile-main">
        <text class="name">{{ store.user.name }}</text>
        <text class="meta">{{ store.user.student_id }} · {{ store.user.class_name }}</text>
      </view>
      <view class="profile-actions"><text class="admin" @click="enableNotifications">通知设置</text><text v-if="store.isAdmin" class="admin" @click="goAdmin">管理后台</text></view>
    </view>

    <scroll-view scroll-x class="tabs">
      <view class="tabs-inner">
        <text v-for="item in tabs" :key="item.value" class="tab" :class="{ active: tab === item.value }" @click="tab = item.value">{{ item.label }}</text>
      </view>
    </scroll-view>

    <view class="list">
      <view v-for="item in filtered" :key="item.id" class="reservation">
        <view class="reservation-head">
          <view>
            <text class="room">{{ item.room?.room_code }} {{ item.room?.name }}</text>
            <text class="scene">{{ sceneLabel(item.scene) }} · {{ item.usage_mode === 'shared' ? '共享' : '独占' }}</text>
          </view>
          <text class="status" :class="`s-${item.status}`">{{ statusLabel(item.status) }}</text>
        </view>
        <text class="time">{{ item.date }}　{{ minuteTime(item.start_minute) }}–{{ minuteTime(item.end_minute) }}</text>
        <text class="purpose">{{ item.people_count }} 人 · {{ item.purpose }}</text>
        <text v-if="item.review_note" class="note">备注：{{ item.review_note }}</text>
        <view class="actions">
          <button v-if="['pending','approved'].includes(item.status)" class="btn ghost" @click="cancel(item.id)">取消</button>
          <button v-if="item.status === 'approved'" class="btn primary" @click="doCheckin(item.id)">签到</button>
          <button v-if="['cleanup_pending','cleanup_rejected'].includes(item.status)" class="btn warning" @click="uploadCleanup(item)">
            {{ item.cleanup ? '重新上传清扫照片' : '上传清扫照片' }}
          </button>
        </view>
      </view>
      <view v-if="!filtered.length" class="empty">暂无相关预约</view>
    </view>

    <button class="reserve-fab" @click="goReserve">＋ 发起预约</button>
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useUserStore } from '@/store/user.js'
import { bindWechat, cancelReservation, checkin, getBookingConfig, getMyReservations, getNotificationTemplates, submitCleanup, uploadCleanupPhoto } from '@/api/index.js'

const store = useUserStore()
const reservations = ref([])
const tab = ref('all')
const config = reactive({ open_hour: 8, slot_minutes: 30 })
const tabs = [
  { value: 'all', label: '全部' }, { value: 'pending', label: '待审核' },
  { value: 'approved', label: '待使用' }, { value: 'cleanup', label: '待清扫' },
  { value: 'completed', label: '已完成' },
]
const filtered = computed(() => tab.value === 'all' ? reservations.value : tab.value === 'cleanup'
  ? reservations.value.filter(item => ['cleanup_pending', 'cleanup_rejected'].includes(item.status))
  : reservations.value.filter(item => item.status === tab.value))

function minuteTime(value) {
  const minutes = value ?? 0
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}
function sceneLabel(value) { return ({ study: '自习', meeting: '开会', event: '大型活动', music: '音乐练习' })[value] || '历史预约' }
function statusLabel(value) { return ({ pending: '待审核', approved: '已通过', rejected: '未通过', cancelled: '已取消', in_use: '使用中', cleanup_pending: '待清扫复核', cleanup_rejected: '清扫未通过', completed: '已完成', missed: '未签到' })[value] || value }

async function load() {
  try {
    await store.fetchUser()
    Object.assign(config, await getBookingConfig())
    reservations.value = await getMyReservations()
  } catch (_) {}
}
async function cancel(id) {
  const result = await new Promise(resolve => uni.showModal({ title: '确认取消', content: '取消后将释放该时段', success: resolve }))
  if (!result.confirm) return
  await cancelReservation(id); await load()
}
async function doCheckin(id) { await checkin(id); uni.showToast({ title: '签到成功', icon: 'success' }); await load() }
async function uploadCleanup(item) {
  const choice = await new Promise((resolve, reject) => uni.chooseImage({ count: 3, sizeType: ['compressed'], sourceType: ['camera', 'album'], success: resolve, fail: reject }))
  uni.showLoading({ title: '上传中' })
  try {
    const urls = []
    for (const path of choice.tempFilePaths) urls.push((await uploadCleanupPhoto(path)).url)
    await submitCleanup(item.id, urls)
    uni.showToast({ title: '已提交复核', icon: 'success' })
    await load()
  } finally { uni.hideLoading() }
}
function goAdmin() { uni.navigateTo({ url: '/pages/admin/dashboard' }) }
function goReserve() { uni.navigateTo({ url: '/pages/reserve/reserve' }) }
async function enableNotifications() {
  // #ifdef MP-WEIXIN
  try {
    const loginResult = await uni.login({ provider: 'weixin' })
    await bindWechat(loginResult.code)
    const { template_ids } = await getNotificationTemplates()
    if (!template_ids.length) return uni.showToast({ title: '服务器尚未配置消息模板', icon: 'none' })
    for (let index = 0; index < template_ids.length; index += 3) {
      await wx.requestSubscribeMessage({ tmplIds: template_ids.slice(index, index + 3) })
    }
    uni.showToast({ title: '通知设置完成', icon: 'success' })
  } catch (_) { uni.showToast({ title: '未完成通知授权', icon: 'none' }) }
  // #endif
  // #ifndef MP-WEIXIN
  uni.showToast({ title: '请在微信小程序中设置', icon: 'none' })
  // #endif
}
onShow(load)
</script>

<style scoped>
.page{min-height:100vh;background:#f4f6f8;padding-bottom:130rpx}.profile{display:flex;align-items:center;padding:42rpx 30rpx;background:linear-gradient(135deg,#174d35,#287253);color:#fff}.avatar{width:82rpx;height:82rpx;border-radius:50%;background:rgba(255,255,255,.18);display:flex;align-items:center;justify-content:center;font-size:34rpx;font-weight:700}.profile-main{flex:1;margin-left:20rpx}.name{display:block;font-size:34rpx;font-weight:700}.meta{font-size:23rpx;opacity:.75}.admin{padding:10rpx 16rpx;border:1rpx solid rgba(255,255,255,.5);border-radius:10rpx;font-size:22rpx}.tabs{white-space:nowrap;background:#fff}.tabs-inner{display:flex;padding:0 16rpx}.tab{padding:24rpx 20rpx;font-size:25rpx;color:#758079}.tab.active{color:#1a6b47;font-weight:700;border-bottom:4rpx solid #1a6b47}.list{padding:20rpx}.reservation{background:#fff;border-radius:18rpx;padding:24rpx;margin-bottom:16rpx}.reservation-head{display:flex;justify-content:space-between}.room{display:block;font-size:29rpx;font-weight:700}.scene{font-size:21rpx;color:#8b958f}.status{font-size:21rpx;padding:7rpx 12rpx;border-radius:20rpx;background:#edf0ee}.s-pending{color:#a66b00;background:#fff4d8}.s-approved,.s-completed{color:#157a4d;background:#e8f7ef}.s-rejected,.s-cleanup_rejected,.s-missed{color:#b53535;background:#fdecec}.s-cleanup_pending{color:#985f00;background:#fff2d4}.time,.purpose,.note{display:block;margin-top:12rpx;font-size:24rpx;color:#5d6962}.note{padding:12rpx;background:#f6f7f6;border-radius:8rpx;color:#8a6552}.actions{display:flex;justify-content:flex-end;gap:12rpx;margin-top:18rpx}.btn{margin:0;padding:0 22rpx;line-height:62rpx;font-size:23rpx;border-radius:10rpx}.ghost{background:#f0f2f1;color:#65716a}.primary{background:#1a6b47;color:#fff}.warning{background:#dc7d19;color:#fff}.empty{text-align:center;color:#9ca49f;padding:100rpx}.reserve-fab{position:fixed;right:28rpx;bottom:110rpx;background:#1a6b47;color:#fff;border-radius:50rpx;padding:0 30rpx;font-size:25rpx;box-shadow:0 8rpx 28rpx rgba(26,107,71,.28)}
.profile-actions{display:flex;flex-direction:column;gap:8rpx}.profile-actions .admin{padding:7rpx 11rpx;font-size:19rpx;text-align:center}
</style>
