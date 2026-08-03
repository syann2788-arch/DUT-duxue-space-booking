<template>
  <view class="page">
    <view class="hero"><text class="title">管理后台</text><text class="sub">预约、清扫与系统规则统一管理</text></view>
    <view class="stats">
      <view v-for="item in statItems" :key="item.key" class="stat"><text class="num">{{ stats[item.key] || 0 }}</text><text>{{ item.label }}</text></view>
    </view>
    <view class="menu">
      <view v-for="item in menus" :key="item.url" class="menu-item" @click="go(item.url)">
        <text class="icon">{{ item.icon }}</text><view class="menu-main"><text class="menu-title">{{ item.title }}</text><text class="menu-desc">{{ item.desc }}</text></view><text>›</text>
      </view>
      <view class="menu-item" @click="downloadExport"><text class="icon">📊</text><view class="menu-main"><text class="menu-title">导出预约数据</text><text class="menu-desc">下载完整 Excel 文件</text></view><text>›</text></view>
    </view>
  </view>
</template>
<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { downloadExport, getAdminStats } from '@/api/index.js'
const stats = ref({})
const statItems = [{ key:'today',label:'今日预约' },{ key:'pending',label:'待审核' },{ key:'cleanup_pending',label:'待复核' },{ key:'total_users',label:'总用户' }]
const menus = [
  { icon:'✅',title:'预约审核',desc:'单条或批量通过/驳回',url:'/pages/admin/reservations' },
  { icon:'🧹',title:'清扫复核',desc:'查看现场照片并处理',url:'/pages/admin/cleanup' },
  { icon:'👥',title:'用户与限制',desc:'临时、限时、永久封禁',url:'/pages/admin/users' },
  { icon:'⚙️',title:'系统配置',desc:'时段、上限、自动审批与分房规则',url:'/pages/admin/settings' },
  { icon:'📋',title:'辅导员管理',desc:'CSV 导入辅导员账号',url:'/pages/admin/counselors' },
]
function go(url){uni.navigateTo({url})}
onShow(async()=>{stats.value=await getAdminStats()})
</script>
<style scoped>
.page{min-height:100vh;background:#f5f6f8}.hero{padding:44rpx 30rpx;background:#263b32;color:#fff}.title{display:block;font-size:40rpx;font-weight:700}.sub{font-size:23rpx;opacity:.7}.stats{display:grid;grid-template-columns:1fr 1fr;gap:14rpx;padding:20rpx}.stat{background:#fff;border-radius:16rpx;padding:24rpx;color:#7d8882}.num{display:block;font-size:38rpx;font-weight:700;color:#1a6b47}.menu{padding:0 20rpx 30rpx}.menu-item{display:flex;align-items:center;background:#fff;padding:24rpx;margin-bottom:12rpx;border-radius:16rpx}.icon{font-size:36rpx;margin-right:20rpx}.menu-main{flex:1}.menu-title{display:block;font-size:28rpx;font-weight:700}.menu-desc{font-size:22rpx;color:#929b96}
</style>
