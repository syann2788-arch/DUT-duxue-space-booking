<template>
  <view class="page">
    <view class="card" v-if="room">
      <text class="room-code">{{ room.room_code }}</text>
      <text class="room-name">{{ room.name }}</text>
      <view class="tags">
        <text class="tag">{{ room.category }}</text>
        <text class="tag tag-info" v-if="room.has_fridge">有冰箱</text>
        <text class="tag tag-info" v-if="room.has_instruments">有乐器</text>
      </view>
      <text class="desc">{{ room.description }}</text>

      <!-- Public room: show status, admin can change -->
      <view class="public-box" v-if="room.is_public">
        <text class="public-status-label">当前状态：</text>
        <text class="public-status" :class="statusClass">{{ statusText }}</text>
        <view class="admin-btns" v-if="store.isAdmin">
          <button class="btn-sm" @click="setPublicStatus('free')">空闲</button>
          <button class="btn-sm btn-warn" @click="setPublicStatus('busy')">较满</button>
          <button class="btn-sm btn-danger" @click="setPublicStatus('crowded')">已满</button>
        </view>
      </view>

      <!-- Non-reservable (display only) -->
      <view class="notice" v-else-if="!room.can_reserve">
        <text class="notice-text">该空间不对外开放预约</text>
      </view>

      <!-- Reservable -->
      <view v-else>
        <text class="rule-text" v-if="room.who_can_reserve === 'counselor'">仅限辅导员预约</text>
        <button class="btn-primary reserve-btn" @click="goReserve"
          v-if="canReserve">
          预约该空间
        </button>
        <text class="notice-text" v-else>暂无预约权限（需要{{ room.who_can_reserve === 'counselor' ? '辅导员' : '相应' }}权限）</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { useUserStore } from '@/store/user.js'
import { getRoomDetail, setPublicStatus as apiSetPublicStatus } from '@/api/index.js'

const store = useUserStore()
const room = ref(null)

const statusClass = computed(() => {
  if (!room.value?.public_status) return ''
  return room.value.public_status === 'free' ? 'status-free'
    : room.value.public_status === 'busy' ? 'status-busy' : 'status-crowded'
})

const statusText = computed(() => {
  const map = { free: '空闲', busy: '较满', crowded: '已满' }
  return map[room.value?.public_status] || '未知'
})

const canReserve = computed(() => {
  if (!room.value) return false
  if (room.value.who_can_reserve === 'all') return true
  if (room.value.who_can_reserve === 'counselor') return store.isCounselor
  return false
})

onLoad(async (opt) => {
  try { room.value = await getRoomDetail(opt.id) } catch {}
})

async function setPublicStatus(status) {
  try {
    await apiSetPublicStatus(room.value.id, status)
    room.value.public_status = status
    uni.showToast({ title: '状态已更新', icon: 'success' })
  } catch {}
}

function goReserve() {
  uni.navigateTo({ url: `/pages/reserve/reserve?roomId=${room.value.id}&roomName=${encodeURIComponent(room.value.name)}` })
}
</script>

<style scoped>
.page { padding-bottom: 40rpx; }
.room-code { font-size: 48rpx; font-weight: 700; color: #F25B15; }
.room-name { font-size: 32rpx; color: #667180; display: block; margin-top: 4rpx; }
.tags { display: flex; gap: 12rpx; margin-top: 16rpx; flex-wrap: wrap; }
.tag {
  background: #FEF1EA;
  color: #B8430A;
  font-size: 22rpx;
  padding: 6rpx 16rpx;
  border-radius: 9999rpx;
}
.tag-info { background: #E9EFFA; color: #3D6FD1; }
.desc { font-size: 28rpx; color: #454F5E; margin-top: 20rpx; line-height: 1.6; }

.public-box {
  background: #F6F7F9;
  padding: 24rpx;
  border-radius: 12rpx;
  margin-top: 24rpx;
}
.public-status-label { font-size: 26rpx; color: #667180; }
.public-status { font-size: 32rpx; font-weight: 700; margin-left: 8rpx; }
.admin-btns { display: flex; gap: 12rpx; margin-top: 16rpx; }
.btn-sm {
  flex: 1;
  padding: 12rpx;
  font-size: 24rpx;
  border-radius: 9999rpx;
  background: #0E9868;
  color: #fff;
  border: none;
}
.btn-warn { background: #F25B15; }
.btn-danger { background: #CE3F36; }

.notice { margin-top: 24rpx; padding: 24rpx; background: #FBECEB; border-radius: 12rpx; border: 1rpx solid #F3CBC8; }
.notice-text { font-size: 26rpx; color: #CE3F36; }
.rule-text { font-size: 24rpx; color: #CE3F36; display: block; margin-top: 16rpx; }
.reserve-btn { width: 100%; margin-top: 24rpx; box-shadow: 0 5px 12px rgba(242,91,21,0.22); }
</style>
