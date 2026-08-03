<template><view class="page">
  <view class="filters">
    <picker :range="statusLabels" :value="statusIndex" @change="statusIndex=Number($event.detail.value);load()"><view class="pick">状态：{{statusLabels[statusIndex]}} ›</view></picker>
    <picker :range="sceneLabels" :value="sceneIndex" @change="sceneIndex=Number($event.detail.value);load()"><view class="pick">场景：{{sceneLabels[sceneIndex]}} ›</view></picker>
    <view class="date-row"><picker mode="date" :value="dateFrom" @change="dateFrom=$event.detail.value"><view class="pick">开始：{{dateFrom||'不限'}} ›</view></picker><picker mode="date" :value="dateTo" @change="dateTo=$event.detail.value"><view class="pick">结束：{{dateTo||'不限'}} ›</view></picker></view>
    <view class="filter-actions"><button @click="load">查询</button><button class="export" @click="exportData">导出Excel</button></view>
  </view>
  <view class="toolbar"><text>共 {{items.length}} 条</text><button v-if="currentStatus==='pending'" class="small" @click="toggleAll">{{selected.length===items.length?'取消全选':'全选'}}</button></view>
  <view v-for="item in items" :key="item.id" class="card" @click="currentStatus==='pending'&&toggle(item.id)">
    <view class="head"><checkbox v-if="currentStatus==='pending'" :checked="selected.includes(item.id)" color="#1a6b47"/><text class="room">{{item.room.room_code}} {{item.room.name}}</text><text>{{scene(item.scene)}}</text></view>
    <text>{{item.user.name}} · {{item.user.student_id}} · {{item.user.phone}} · {{item.people_count}}人</text>
    <text>{{item.date}}　{{clock(item.start_minute)}}–{{clock(item.end_minute)}}</text><text class="purpose">{{item.purpose}}</text>
    <image v-if="item.campus_card_photo_url" class="campus-card" :src="server+item.campus_card_photo_url" mode="aspectFill" @click.stop="previewCard(item)"/>
    <text v-if="item.review_note" class="note">审核备注：{{item.review_note}}</text>
  </view>
  <view v-if="!items.length" class="empty">暂无匹配记录</view>
  <view v-if="currentStatus==='pending'" class="bottom"><button class="reject" :disabled="!selected.length" @click="review('rejected')">批量驳回</button><button class="approve" :disabled="!selected.length" @click="review('approved')">批量通过</button></view>
</view></template>

<script setup>
import{computed,ref}from'vue';import{onShow}from'@dcloudio/uni-app';import{downloadExport,getAllReservations,reviewReservations,SERVER_URL}from'@/api/index.js'
const items=ref([]),selected=ref([]),statusIndex=ref(1),sceneIndex=ref(0),dateFrom=ref(''),dateTo=ref(''),server=SERVER_URL
const statuses=[['全部',''],['待审核','pending'],['已通过','approved'],['已驳回','rejected'],['使用中','in_use'],['待清扫','cleanup_pending'],['清扫不合格','cleanup_rejected'],['已完结','completed'],['违约','missed']]
const scenes=[['全部',''],['自习','study'],['开会','meeting'],['大型活动','event'],['音乐练习','music']]
const statusLabels=statuses.map(x=>x[0]),sceneLabels=scenes.map(x=>x[0]),currentStatus=computed(()=>statuses[statusIndex.value][1])
const scene=v=>({study:'自习',meeting:'开会',event:'大型活动',music:'音乐练习'})[v];const clock=v=>`${String(Math.floor(v/60)).padStart(2,'0')}:${String(v%60).padStart(2,'0')}`
const filters=()=>({date_from:dateFrom.value,date_to:dateTo.value,scene:scenes[sceneIndex.value][1]})
async function load(){items.value=await getAllReservations(null,currentStatus.value,filters());selected.value=[]}
function toggle(id){selected.value=selected.value.includes(id)?selected.value.filter(x=>x!==id):[...selected.value,id]}
function toggleAll(){selected.value=selected.value.length===items.value.length?[]:items.value.map(x=>x.id)}
function previewCard(item){uni.previewImage({urls:[server+item.campus_card_photo_url]})}
function exportData(){downloadExport({...filters(),status_filter:currentStatus.value})}
async function review(decision){const r=await new Promise(resolve=>uni.showModal({title:decision==='approved'?'通过申请':'驳回申请',editable:true,placeholderText:'审核备注（可选）',success:resolve}));if(!r.confirm)return;await reviewReservations({reservation_ids:selected.value,decision,note:r.content||''});uni.showToast({title:'处理成功',icon:'success'});await load()}
onShow(load)
</script>

<style scoped>
.page{padding:20rpx 20rpx 140rpx;background:#f5f6f8;min-height:100vh}.filters{background:#fff;padding:20rpx;border-radius:16rpx;margin-bottom:14rpx}.pick{padding:15rpx;background:#f5f7f6;border-radius:9rpx;font-size:23rpx;margin-bottom:10rpx}.date-row,.filter-actions{display:flex;gap:10rpx}.date-row picker,.filter-actions button{flex:1}.filter-actions button{font-size:22rpx;line-height:60rpx}.export{background:#1a6b47;color:#fff}.toolbar{display:flex;justify-content:space-between;align-items:center;padding:12rpx}.small{margin:0;font-size:22rpx;line-height:54rpx}.card{background:#fff;border-radius:16rpx;padding:24rpx;margin-bottom:14rpx;display:flex;flex-direction:column;gap:8rpx;font-size:24rpx;color:#68736d}.head{display:flex;align-items:center;gap:12rpx}.room{flex:1;font-size:28rpx;font-weight:700;color:#263c32}.purpose,.note{padding:12rpx;background:#f5f7f6;border-radius:8rpx}.campus-card{width:220rpx;height:140rpx;border-radius:10rpx;margin-top:8rpx}.note{color:#8a6552}.empty{text-align:center;padding:100rpx;color:#999}.bottom{position:fixed;bottom:0;left:0;right:0;display:flex;gap:16rpx;padding:20rpx;background:#fff}.bottom button{flex:1}.approve{background:#1a6b47;color:#fff}.reject{background:#b64444;color:#fff}
</style>
