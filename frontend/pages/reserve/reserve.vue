<template>
  <view class="page">
    <view class="hero">
      <text class="hero-title">预约书院空间</text>
      <text class="hero-subtitle">选择使用场景，系统按优先级自动分配合适房间</text>
    </view>

    <view class="card">
      <text class="section-title">1. 使用场景</text>
      <view class="scene-grid">
        <view v-for="item in scenes" :key="item.value" class="scene" :class="{ selected: form.scene === item.value }" @click="form.scene = item.value">
          <text class="scene-icon">{{ item.icon }}</text>
          <text class="scene-name">{{ item.label }}</text>
          <text class="scene-desc">{{ item.desc }}</text>
        </view>
      </view>
      <view class="allocation-note">{{ currentScene.allocation }}</view>
    </view>

    <view class="card">
      <text class="section-title">2. 日期与时间</text>
      <picker mode="selector" :range="dateLabels" :value="dateIndex" @change="dateIndex = Number($event.detail.value)">
        <view class="field"><text>预约日期</text><text class="value">{{ dateLabels[dateIndex] }} ›</text></view>
      </picker>
      <view class="time-row">
        <picker class="time-picker" mode="selector" :range="startLabels" :value="startIndex" @change="changeStart">
          <view class="time-box"><text class="muted">开始</text><text>{{ startLabels[startIndex] }}</text></view>
        </picker>
        <text class="dash">—</text>
        <picker class="time-picker" mode="selector" :range="endLabels" :value="endIndex" @change="endIndex = Number($event.detail.value)">
          <view class="time-box"><text class="muted">结束</text><text>{{ endLabels[endIndex] }}</text></view>
        </picker>
      </view>
      <text class="duration">本次 {{ durationMinutes / 60 }} 小时 · 每日累计上限 {{ config.max_minutes_per_day / 60 }} 小时</text>
    </view>

    <view v-if="form.scene !== 'study'" class="card">
      <text class="section-title">3. 使用信息</text>
      <view class="field">
        <text>使用人数</text>
        <input class="number-input" type="number" v-model.number="form.people_count" placeholder="请输入人数" />
      </view>
      <textarea class="purpose" v-model="form.purpose" maxlength="300" placeholder="请说明活动内容、课程或会议用途（必填）" />
      <text class="counter">至少10字 · {{ form.purpose.length }}/300</text>
    </view>

    <view class="card">
      <text class="section-title">{{ form.scene === 'study' ? '3' : '4' }}. 玉兰卡核验</text>
      <text class="upload-hint">必须上传本人玉兰卡清晰实拍照片，管理员仅用于身份核验。</text>
      <image v-if="campusCardLocal" class="card-photo" :src="campusCardLocal" mode="aspectFill" @click="chooseCampusCard" />
      <button v-else class="upload" @click="chooseCampusCard">拍照或选择玉兰卡照片</button>
      <text v-if="campusCardUrl" class="uploaded">✓ 已上传，可提交预约</text>
    </view>

    <view class="rules">
      <text>提交后进入待审核队列；每日 23:00 自动通过仍未处理的申请。</text>
      <text>结束使用后上传清扫照片即可发起下一次预约，管理员随后复核。</text>
      <text>音乐练习优先分配 B102；A103 钢琴仅在15:00–21:00开放，并与大型活动互斥。</text>
    </view>

    <button class="submit" :loading="submitting" :disabled="submitting" @click="submit">提交预约申请</button>
  </view>
</template>

<script setup>
import { computed, reactive, ref, onMounted, watch } from 'vue'
import { bindWechat, createReservation, getBookingConfig, getNotificationTemplates, uploadCampusCardPhoto } from '@/api/index.js'

const scenes = [
  { value: 'study', label: '自习', icon: '📚', desc: '共享使用', allocation: '优先分配：A102 → A101 → A105' },
  { value: 'meeting', label: '开会', icon: '👥', desc: '独占使用', allocation: '优先分配：A105 → A101 → A102' },
  { value: 'event', label: '大型活动', icon: '🎤', desc: 'A103 独占', allocation: '仅 A103；与 A103 钢琴练习时段互斥' },
  { value: 'music', label: '音乐练习', icon: '🎵', desc: '独占使用', allocation: 'B102 优先；A103 钢琴15:00–21:00可用' },
]
const config = reactive({ open_hour: 8, close_hour: 22, slot_minutes: 30, max_minutes_per_day: 240, advance_days: 7 })
const form = reactive({ scene: 'study', people_count: 1, purpose: '' })
const dateIndex = ref(0)
const startIndex = ref(0)
const endIndex = ref(0)
const submitting = ref(false)
const campusCardLocal = ref('')
const campusCardUrl = ref('')

const currentScene = computed(() => scenes.find(item => item.value === form.scene))
const dates = computed(() => Array.from({ length: config.advance_days + 1 }, (_, index) => {
  const value = new Date(); value.setDate(value.getDate() + index)
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`
}))
const dateLabels = computed(() => dates.value.map((value, index) => `${value} ${index === 0 ? '今天' : index === 1 ? '明天' : ''}`))
const totalSlots = computed(() => (config.close_hour - config.open_hour) * 60 / config.slot_minutes)
const timeAt = slot => {
  const minutes = config.open_hour * 60 + slot * config.slot_minutes
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}
const startLabels = computed(() => Array.from({ length: totalSlots.value }, (_, index) => timeAt(index)))
const endLabels = computed(() => Array.from({ length: totalSlots.value - startIndex.value }, (_, index) => timeAt(startIndex.value + index + 1)))
const durationMinutes = computed(() => (endIndex.value + 1) * config.slot_minutes)

function changeStart(event) {
  startIndex.value = Number(event.detail.value)
  endIndex.value = 0
}

watch(() => form.scene, scene => {
  if (scene === 'study') {
    form.people_count = 1
    form.purpose = ''
  }
})

async function chooseCampusCard() {
  const picked = await new Promise(resolve => uni.chooseImage({ count: 1, sizeType: ['compressed'], sourceType: ['camera', 'album'], success: resolve, fail: () => resolve(null) }))
  if (!picked?.tempFilePaths?.[0]) return
  uni.showLoading({ title: '上传中' })
  try {
    campusCardLocal.value = picked.tempFilePaths[0]
    campusCardUrl.value = (await uploadCampusCardPhoto(campusCardLocal.value)).url
  } catch (_) {
    campusCardLocal.value = ''
    campusCardUrl.value = ''
    uni.showToast({ title: '玉兰卡照片上传失败', icon: 'none' })
  } finally { uni.hideLoading() }
}

async function setupWechatNotifications() {
  // #ifdef MP-WEIXIN
  try {
    const loginResult = await uni.login({ provider: 'weixin' })
    await bindWechat(loginResult.code)
    const { template_ids } = await getNotificationTemplates()
    for (let index = 0; index < template_ids.length; index += 3) {
      await wx.requestSubscribeMessage({ tmplIds: template_ids.slice(index, index + 3) })
    }
  } catch (_) { /* Notification permission must not block a reservation. */ }
  // #endif
}

async function submit() {
  if (form.scene !== 'study' && (!form.people_count || form.people_count < 1)) return uni.showToast({ title: '请填写使用人数', icon: 'none' })
  if (form.scene !== 'study' && form.purpose.trim().length < 10) return uni.showToast({ title: '申请理由至少填写10个字', icon: 'none' })
  if (!campusCardUrl.value) return uni.showToast({ title: '请先上传玉兰卡照片', icon: 'none' })
  if (durationMinutes.value > config.max_minutes_per_day) return uni.showToast({ title: '本次时长超过单日上限', icon: 'none' })
  submitting.value = true
  try {
    await setupWechatNotifications()
    const reservation = await createReservation({
      scene: form.scene,
      date: dates.value[dateIndex.value],
      start_slot: startIndex.value,
      end_slot: startIndex.value + endIndex.value + 1,
      people_count: Number(form.people_count),
      purpose: form.scene === 'study' ? '个人自习' : form.purpose.trim(),
      campus_card_photo_url: campusCardUrl.value,
    })
    await new Promise(resolve => uni.showModal({ title: '提交成功', content: `已分配 ${reservation.room.room_code} ${reservation.room.name}，等待审核`, showCancel: false, success: resolve }))
    uni.switchTab({ url: '/pages/my/my' })
  } finally { submitting.value = false }
}

onMounted(async () => {
  Object.assign(config, await getBookingConfig())
  const now = new Date()
  const minutesNow = now.getHours() * 60 + now.getMinutes()
  const firstFutureSlot = Math.max(0, Math.ceil((minutesNow - config.open_hour * 60) / config.slot_minutes))
  if (firstFutureSlot >= totalSlots.value && config.advance_days >= 1) {
    dateIndex.value = 1
    startIndex.value = 0
  } else {
    startIndex.value = Math.min(firstFutureSlot, totalSlots.value - 1)
  }
  endIndex.value = 0
})
</script>

<style scoped>
.page{padding:24rpx 24rpx 60rpx;background:#f4f6f8;min-height:100vh}.hero{padding:28rpx 8rpx}.hero-title{display:block;font-size:42rpx;font-weight:700;color:#173f2d}.hero-subtitle{display:block;margin-top:8rpx;font-size:24rpx;color:#718078}.card{background:#fff;border-radius:20rpx;padding:28rpx;margin-bottom:20rpx;box-shadow:0 8rpx 30rpx rgba(20,60,40,.05)}.section-title{display:block;font-size:28rpx;font-weight:700;margin-bottom:22rpx}.scene-grid{display:grid;grid-template-columns:1fr 1fr;gap:16rpx}.scene{padding:22rpx;border:2rpx solid #e7ece9;border-radius:16rpx;display:flex;flex-direction:column}.scene.selected{border-color:#1a6b47;background:#eef8f3}.scene-icon{font-size:38rpx}.scene-name{font-size:28rpx;font-weight:700;margin-top:8rpx}.scene-desc{font-size:21rpx;color:#87928c}.allocation-note{margin-top:18rpx;padding:16rpx;background:#f6f8f7;border-radius:10rpx;font-size:23rpx;color:#496356}.field{height:88rpx;border-bottom:1rpx solid #edf0ee;display:flex;align-items:center;justify-content:space-between;font-size:26rpx}.value{color:#1a6b47}.time-row{display:flex;align-items:center;gap:16rpx;margin-top:22rpx}.time-picker{flex:1}.time-box{padding:20rpx;background:#f6f8f7;border-radius:12rpx;display:flex;flex-direction:column;gap:5rpx}.muted,.duration,.counter,.upload-hint{font-size:21rpx;color:#8a9690}.dash{color:#9aa29e}.duration{display:block;margin-top:14rpx}.number-input{text-align:right;width:180rpx}.purpose{box-sizing:border-box;width:100%;height:180rpx;margin-top:20rpx;padding:18rpx;background:#f6f8f7;border-radius:12rpx;font-size:25rpx}.counter{display:block;text-align:right}.upload-hint{display:block;margin-bottom:18rpx;line-height:1.6}.upload{background:#eef6f2;color:#1a6b47;font-size:24rpx}.card-photo{width:100%;height:300rpx;border-radius:12rpx}.uploaded{display:block;margin-top:12rpx;color:#1a6b47;font-size:22rpx}.rules{padding:8rpx 12rpx 24rpx}.rules text{display:block;font-size:22rpx;color:#6f7b75;line-height:1.8}.submit{background:#1a6b47!important;color:#fff!important;border-radius:14rpx;font-size:29rpx;font-weight:600}
</style>
