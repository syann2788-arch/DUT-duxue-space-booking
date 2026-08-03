<template><view class="page">
  <view class="toolbar"><text>待审核 {{ items.length }} 条</text><button class="small" @click="toggleAll">{{ selected.length===items.length?'取消全选':'全选' }}</button></view>
  <view v-for="item in items" :key="item.id" class="card" @click="toggle(item.id)">
    <view class="head"><checkbox :checked="selected.includes(item.id)" color="#1a6b47"/><text class="room">{{item.room.room_code}} {{item.room.name}}</text><text>{{scene(item.scene)}}</text></view>
    <text>{{item.user.name}} · {{item.user.student_id}} · {{item.people_count}}人</text>
    <text>{{item.date}}　{{clock(item.start_minute)}}–{{clock(item.end_minute)}}</text><text class="purpose">{{item.purpose}}</text>
  </view>
  <view v-if="!items.length" class="empty">暂无待审核申请</view>
  <view class="bottom"><button class="reject" :disabled="!selected.length" @click="review('rejected')">批量驳回</button><button class="approve" :disabled="!selected.length" @click="review('approved')">批量通过</button></view>
</view></template>
<script setup>
import {ref} from 'vue';import{onShow}from'@dcloudio/uni-app';import{getAllReservations,reviewReservations}from'@/api/index.js'
const items=ref([]),selected=ref([]);const scene=v=>({study:'自习',meeting:'开会',event:'大型活动',music:'音乐练习'})[v];const clock=v=>`${String(Math.floor(v/60)).padStart(2,'0')}:${String(v%60).padStart(2,'0')}`
async function load(){items.value=await getAllReservations(null,'pending');selected.value=[]}function toggle(id){selected.value=selected.value.includes(id)?selected.value.filter(x=>x!==id):[...selected.value,id]}function toggleAll(){selected.value=selected.value.length===items.value.length?[]:items.value.map(x=>x.id)}
async function review(decision){const r=await new Promise(resolve=>uni.showModal({title:decision==='approved'?'通过申请':'驳回申请',editable:true,placeholderText:'审核备注（可选）',success:resolve}));if(!r.confirm)return;await reviewReservations({reservation_ids:selected.value,decision,note:r.content||''});uni.showToast({title:'处理成功',icon:'success'});await load()}onShow(load)
</script>
<style scoped>.page{padding:20rpx 20rpx 140rpx;background:#f5f6f8;min-height:100vh}.toolbar{display:flex;justify-content:space-between;align-items:center;padding:12rpx}.small{margin:0;font-size:22rpx;line-height:54rpx}.card{background:#fff;border-radius:16rpx;padding:24rpx;margin-bottom:14rpx;display:flex;flex-direction:column;gap:8rpx;font-size:24rpx;color:#68736d}.head{display:flex;align-items:center;gap:12rpx}.room{flex:1;font-size:28rpx;font-weight:700;color:#263c32}.purpose{padding:12rpx;background:#f5f7f6;border-radius:8rpx}.empty{text-align:center;padding:100rpx;color:#999}.bottom{position:fixed;bottom:0;left:0;right:0;display:flex;gap:16rpx;padding:20rpx;background:#fff}.bottom button{flex:1}.approve{background:#1a6b47;color:#fff}.reject{background:#b64444;color:#fff}</style>
