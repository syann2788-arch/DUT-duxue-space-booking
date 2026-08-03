<template>
  <view class="page">
    <view class="card">
      <text class="title">导入辅导员名单</text>
      <text class="hint">上传CSV文件，每行一个学号</text>
      <button class="btn-primary" @click="importCsv" :loading="importing">选择CSV文件并导入</button>

      <view class="result" v-if="importResult">
        <text class="result-text">成功设置 {{ importResult.imported_count }} 位辅导员</text>
      </view>
    </view>

    <view class="card">
      <text class="title">辅导员列表（{{ counselors.length }}人）</text>
      <view class="coun-item" v-for="c in counselors" :key="c.id">
        <view class="coun-info">
          <text class="coun-name">{{ c.name }}</text>
          <text class="coun-id">{{ c.student_id }} | {{ c.class_name }}</text>
        </view>
        <text class="coun-phone">{{ c.phone }}</text>
      </view>
      <text class="empty" v-if="counselors.length === 0">暂无辅导员</text>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getCounselors, importCounselors } from '@/api/index.js'

const counselors = ref([])
const importing = ref(false)
const importResult = ref(null)

onMounted(async () => {
  try { counselors.value = await getCounselors() } catch {}
})

async function importCsv() {
  const res = await new Promise((resolve) => {
    uni.chooseFile({
      count: 1,
      type: 'file',
      extension: ['.csv'],
      success: resolve,
      fail: () => resolve(null),
    })
  })
  if (!res || !res.tempFiles?.[0]) return

  importing.value = true
  try {
    const result = await importCounselors(res.tempFiles[0].path)
    importResult.value = result
    counselors.value = await getCounselors()
    uni.showToast({ title: result.message, icon: 'success' })
  } catch {}
  finally { importing.value = false }
}
</script>

<style scoped>
.page { padding-bottom: 40rpx; }
.title { font-size: 28rpx; font-weight: 600; color: #333; margin-bottom: 12rpx; }
.hint { font-size: 24rpx; color: #999; display: block; margin-bottom: 16rpx; }

.result { background: #e8f5e9; padding: 16rpx; border-radius: 8rpx; margin-top: 16rpx; }
.result-text { color: #2e7d32; font-size: 26rpx; }

.coun-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16rpx 0;
  border-bottom: 2rpx solid #f0f0f0;
}
.coun-info { display: flex; flex-direction: column; gap: 4rpx; }
.coun-name { font-size: 28rpx; font-weight: 600; color: #333; }
.coun-id { font-size: 22rpx; color: #999; }
.coun-phone { font-size: 24rpx; color: #666; }
.empty { text-align: center; color: #ccc; font-size: 26rpx; padding: 40rpx 0; }
</style>
