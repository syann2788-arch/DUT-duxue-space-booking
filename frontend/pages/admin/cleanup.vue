<template><view class="page">
  <view v-for="item in items" :key="item.id" class="card"><text class="title">{{item.room.room_code}} {{item.room.name}}</text><text>{{item.user.name}} · {{item.user.student_id}}</text><text>{{item.date}} · {{item.purpose}}</text>
    <view class="photos"><image v-for="(url,index) in item.cleanup.photo_urls" :key="url" :src="server+url" mode="aspectFill" @click="preview(item.cleanup.photo_urls,index)"/></view>
    <view class="actions"><button @click="decide(item,'rejected')">不通过/限制</button><button class="approve" @click="decide(item,'approved')">通过</button></view>
  </view><view v-if="!items.length" class="empty">暂无待复核照片</view>
</view></template>
<script setup>
import{ref}from'vue';import{onShow}from'@dcloudio/uni-app';import{getCleanupQueue,reviewCleanup,SERVER_URL}from'@/api/index.js';const items=ref([]),server=SERVER_URL
async function load(){items.value=await getCleanupQueue()}function preview(urls,index){uni.previewImage({urls:urls.map(x=>server+x),current:index})}
async function decide(item,decision){const note=await new Promise(resolve=>uni.showModal({title:decision==='approved'?'确认清扫合格':'填写不通过原因',editable:true,placeholderText:'复核备注',success:resolve}));if(!note.confirm)return;let data={decision,note:note.content||'',restrict_user:false};if(decision==='rejected'){const action=await new Promise(resolve=>uni.showActionSheet({itemList:['仅退回重传','临时封禁1天','限时封禁7天','永久封禁'],success:r=>resolve(r.tapIndex),fail:()=>resolve(0)}));if(action>0)data={...data,restrict_user:true,restriction_level:action===1?'temporary':action===2?'timed':'permanent',restriction_days:action===1?1:action===2?7:null}}await reviewCleanup(item.cleanup.id,data);uni.showToast({title:'复核完成',icon:'success'});await load()}onShow(load)
</script>
<style scoped>.page{padding:20rpx;background:#f5f6f8;min-height:100vh}.card{background:#fff;padding:24rpx;border-radius:16rpx;margin-bottom:16rpx;display:flex;flex-direction:column;gap:8rpx;font-size:24rpx;color:#6c7771}.title{font-size:29rpx;font-weight:700;color:#263c32}.photos{display:flex;gap:10rpx;margin-top:12rpx}.photos image{width:190rpx;height:150rpx;border-radius:10rpx}.actions{display:flex;gap:12rpx;margin-top:14rpx}.actions button{flex:1;font-size:24rpx}.approve{background:#1a6b47;color:#fff}.empty{text-align:center;padding:100rpx;color:#999}</style>
