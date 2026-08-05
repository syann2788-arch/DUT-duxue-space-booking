<template>
  <view class="page">
    <!-- Header -->
    <view class="header">
      <view class="header-info">
        <text class="welcome" v-if="store.user">欢迎，{{ store.user.name }}</text>
        <text class="subtitle">西山7舍 · 书院空间导引</text>
      </view>
      <view class="header-btns">
        <text class="header-btn" v-if="store.isAdmin" @click="goAdmin">管理</text>
        <text class="header-btn" @click="store.logout()">退出</text>
      </view>
    </view>

    <view class="quick-reserve" @click="goReserve">
      <view><text class="quick-title">发起空间预约</text><text class="quick-desc">按场景自动匹配最合适的房间</text></view>
      <text class="quick-arrow">›</text>
    </view>

    <!-- Legend -->
    <view class="legend">
      <view class="legend-item"><view class="dot green"></view><text>可预约</text></view>
      <view class="legend-item"><view class="dot blue"></view><text>公开空间</text></view>
      <view class="legend-item"><view class="dot gray"></view><text>非公共</text></view>
      <view class="legend-item"><view class="dot red"></view><text>需辅导员</text></view>
    </view>

    <!-- Floor Plan -->
    <view class="floor-plan">
      <text class="section-label">北侧（通道上方）</text>
      <view class="room-row north">
        <view class="room-item non-public" v-for="r in northRooms" :key="r.room_code"
          @click="handleRoomClick(r)">
          <text class="room-code">{{ r.room_code }}</text>
          <text class="room-name">{{ r.name }}</text>
          <text class="room-tag" v-if="r.is_public" :class="publicClass(r)">{{ publicLabel(r) }}</text>
          <text class="room-tag tag-counselor" v-else-if="r.who_can_reserve === 'counselor'">辅导员</text>
          <text class="room-tag tag-reservable" v-else-if="r.can_reserve">可预约</text>
        </view>
      </view>

      <view class="corridor">
        <text class="corridor-text">═══ 主通道 ═══</text>
        <view class="corridor-end left-end"><text class="end-text">西</text></view>
        <view class="corridor-end right-end">
          <text class="end-text">东南门 -> 东</text>
        </view>
      </view>

      <text class="section-label">南侧（通道下方）</text>
      <view class="room-row south">
        <view class="room-item non-public" v-for="r in southRooms" :key="r.room_code"
          @click="handleRoomClick(r)">
          <text class="room-code">{{ r.room_code }}</text>
          <text class="room-name">{{ r.name }}</text>
          <text class="room-tag tag-reservable" v-if="r.can_reserve">可预约</text>
        </view>
      </view>
    </view>

    <!-- Room List Cards -->
    <view class="list-section">
      <text class="section-title">空间列表</text>
      <view class="room-card" v-for="r in reservableRooms" :key="r.id" @click="goRoom(r)">
        <view class="card-left">
          <text class="card-code">{{ r.room_code }}</text>
          <text class="card-name">{{ r.name }}</text>
        </view>
        <view class="card-right">
          <text class="card-category">{{ r.category }}</text>
          <text class="card-arrow">></text>
        </view>
      </view>

      <!-- Public spaces -->
      <text class="section-title" style="margin-top: 24rpx;">公开空间（无需预约）</text>
      <view class="room-card" v-for="r in publicRooms" :key="r.id" @click="goRoom(r)">
        <view class="card-left">
          <text class="card-code">{{ r.room_code }}</text>
          <text class="card-name">{{ r.name }}</text>
        </view>
        <view class="card-right">
          <text class="card-category" :class="publicClass(r)">{{ publicLabel(r) }}</text>
          <text class="card-arrow">></text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useUserStore } from '@/store/user.js'
import { getRooms } from '@/api/index.js'

const store = useUserStore()
const rooms = ref([])

const northRooms = computed(() => {
  const codes = ['C104', 'C102', 'B102', 'B101', 'A106', 'A105', 'A104', 'A102']
  return codes.map(c => rooms.value.find(r => r.room_code === c)).filter(Boolean)
})

const southRooms = computed(() => {
  const codes = ['C103', 'C101', 'A103', 'A101']
  return codes.map(c => rooms.value.find(r => r.room_code === c)).filter(Boolean)
})

const reservableRooms = computed(() =>
  rooms.value.filter(r => r.can_reserve && r.who_can_reserve === 'all')
)

const publicRooms = computed(() =>
  rooms.value.filter(r => r.is_public)
)

function publicClass(r) {
  if (!r.public_status) return ''
  return r.public_status === 'free' ? 'status-free' : r.public_status === 'busy' ? 'status-busy' : 'status-crowded'
}

function publicLabel(r) {
  if (!r.public_status) return '未知'
  const map = { free: '空闲', busy: '较满', crowded: '已满' }
  return map[r.public_status] || '未知'
}

function handleRoomClick(r) {
  if (r.is_active) goRoom(r)
}

function goRoom(r) {
  uni.navigateTo({ url: `/pages/room/room?id=${r.id}` })
}

function goAdmin() {
  uni.navigateTo({ url: '/pages/admin/dashboard' })
}

function goReserve() {
  uni.navigateTo({ url: '/pages/reserve/reserve' })
}

onMounted(async () => {
  await store.fetchUser()
  try { rooms.value = await getRooms() } catch {}
})
</script>

<style scoped>
.page { padding-bottom: 40rpx; }
.quick-reserve { margin: 16rpx 20rpx; padding: 26rpx; border-radius: 16rpx; background: linear-gradient(135deg,#6B46C1,#F25B15); color:#fff; display:flex; align-items:center; justify-content:space-between; box-shadow: 0 5px 12px rgba(242,91,21,0.22); }
.quick-title { display:block; font-size:30rpx; font-weight:700; }
.quick-desc { display:block; margin-top:4rpx; font-size:22rpx; opacity:.85; }
.quick-arrow { font-size:48rpx; }

.header {
  background: linear-gradient(135deg, #6B46C1, #F25B15);
  padding: 40rpx 32rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-info { display: flex; flex-direction: column; }
.welcome { color: #fff; font-size: 36rpx; font-weight: 700; }
.subtitle { color: rgba(255,255,255,0.85); font-size: 24rpx; margin-top: 4rpx; }
.header-btns { display: flex; gap: 24rpx; }
.header-btn { color: #fff; font-size: 26rpx; padding: 8rpx 16rpx; border: 2rpx solid rgba(255,255,255,0.5); border-radius: 9999rpx; }

.legend {
  display: flex;
  justify-content: center;
  gap: 32rpx;
  padding: 20rpx;
  background: #fff;
  margin: 16rpx 20rpx;
  border-radius: 12rpx;
  border: 1rpx solid #ECEEF2;
}
.legend-item { display: flex; align-items: center; gap: 8rpx; font-size: 22rpx; color: #667180; }
.dot { width: 16rpx; height: 16rpx; border-radius: 4rpx; }
.dot.green { background: #0E9868; }
.dot.blue { background: #3D6FD1; }
.dot.gray { background: #A9B1BD; }
.dot.red { background: #CE3F36; }

.floor-plan {
  background: #fff;
  margin: 16rpx 20rpx;
  padding: 24rpx 16rpx;
  border-radius: 16rpx;
  border: 1rpx solid #ECEEF2;
}
.section-label { text-align: center; font-size: 22rpx; color: #A9B1BD; display: block; margin: 8rpx 0; }
.room-row { display: flex; flex-wrap: wrap; gap: 8rpx; justify-content: center; padding: 8rpx 0; }
.room-item {
  width: 150rpx;
  padding: 12rpx 8rpx;
  border-radius: 10rpx;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4rpx;
}
.room-item:active { opacity: 0.7; }
.room-code { font-size: 22rpx; font-weight: 700; color: #171C24; }
.room-name { font-size: 20rpx; color: #667180; }
.room-tag { font-size: 18rpx; padding: 2rpx 8rpx; border-radius: 9999rpx; }

.non-public { background: #F6F7F9; }
.reservable { background: #e8f5e9; }
.tag-reservable { background: #0E9868; color: #fff; }
.tag-counselor { background: #CE3F36; color: #fff; }
.status-free { background: #0E9868; color: #fff; }
.status-busy { background: #F25B15; color: #fff; }
.status-crowded { background: #CE3F36; color: #fff; }

.corridor {
  background: #fafafa;
  padding: 16rpx;
  text-align: center;
  border-top: 2rpx dashed #ECEEF2;
  border-bottom: 2rpx dashed #ECEEF2;
  margin: 12rpx 0;
  position: relative;
}
.corridor-text { font-size: 24rpx; color: #A9B1BD; }
.corridor-end { position: absolute; top: 50%; transform: translateY(-50%); }
.left-end { left: 8rpx; }
.right-end { right: 8rpx; }
.end-text { font-size: 20rpx; color: #A9B1BD; }

.list-section { margin-top: 8rpx; }
.section-title { font-size: 28rpx; font-weight: 600; color: #171C24; padding: 24rpx 20rpx 12rpx; }
.room-card {
  background: #fff;
  margin: 8rpx 20rpx;
  padding: 24rpx;
  border-radius: 12rpx;
  border: 1rpx solid #ECEEF2;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.room-card:active { background: #f9f9f9; }
.card-left { display: flex; flex-direction: column; gap: 4rpx; }
.card-code { font-size: 28rpx; font-weight: 700; color: #F25B15; }
.card-name { font-size: 24rpx; color: #667180; }
.card-right { display: flex; align-items: center; gap: 12rpx; }
.card-category { font-size: 24rpx; color: #667180; }
.card-arrow { font-size: 24rpx; color: #A9B1BD; }
</style>
