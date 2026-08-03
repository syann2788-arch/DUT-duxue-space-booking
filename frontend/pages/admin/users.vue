<template>
  <view class="page">
    <view class="search"><input v-model="keyword" placeholder="姓名、学号、手机号或班级" confirm-type="search" @confirm="load"/><button @click="load">搜索</button></view>
    <view class="rule-tip">不设信用分；每累计3次有效违约，系统自动禁约30天。管理员仍可单独设置临时、限时或永久限制。</view>
    <view v-for="user in users" :key="user.id" class="card">
      <view class="main">
        <text class="name">{{user.name}} <text class="role">{{role(user.role)}}</text></text>
        <text>{{user.student_id}} · {{user.class_name}} · {{user.phone}}</text>
        <text v-if="user.role==='student'" class="violations" @click="showViolations(user)">有效违约记录：{{(violationMap[user.id]||[]).length}} 次 ›</text>
        <view v-for="item in activeRestrictions[user.id]||[]" :key="item.id" class="restriction"><text>{{restrictionLabel(item)}} · {{item.reason}}</text><text class="revoke" @click="revoke(item.id)">解除</text></view>
      </view>
      <button v-if="user.role==='student'" class="restrict" @click="restrict(user)">设置限制</button>
    </view>
    <view v-if="!users.length" class="empty">没有匹配的用户</view>
  </view>
</template>

<script setup>
import{ref}from'vue';import{onShow}from'@dcloudio/uni-app';import{addRestriction,getRestrictions,getUsers,getViolations,revokeRestriction}from'@/api/index.js'
const users=ref([]),keyword=ref(''),activeRestrictions=ref({}),violationMap=ref({})
const role=v=>({student:'学生',counselor:'辅导员',admin:'管理员'})[v]
const violationName=v=>v==='no_show'?'未按时签到':'清扫核验不合格'
const restrictionLabel=item=>item.level==='permanent'?'永久封禁':`${item.level==='temporary'?'临时':'限时'}封禁至 ${item.ends_at?.slice(0,10)}`
async function load(){users.value=await getUsers(keyword.value.trim());const students=users.value.filter(x=>x.role==='student');const pairs=await Promise.all(students.map(async x=>[x.id,(await getRestrictions(x.id)).filter(r=>r.is_active)]));activeRestrictions.value=Object.fromEntries(pairs);const violationPairs=await Promise.all(students.map(async x=>[x.id,await getViolations(x.id)]));violationMap.value=Object.fromEntries(violationPairs)}
function showViolations(user){const list=violationMap.value[user.id]||[];uni.showModal({title:`${user.name}的违约记录`,content:list.length?list.map((x,i)=>`${i+1}. ${violationName(x.type)}（${x.created_at.slice(0,10)}）`).join('\n'):'暂无违约记录',showCancel:false})}
async function restrict(user){const pick=await new Promise(resolve=>uni.showActionSheet({itemList:['临时封禁1天','限时封禁7天','限时封禁30天','自定义封禁天数','永久封禁'],success:r=>resolve(r.tapIndex),fail:()=>resolve(-1)}));if(pick<0)return;let options=[['temporary',1],['timed',7],['timed',30],null,['permanent',null]][pick];if(pick===3){const custom=await new Promise(resolve=>uni.showModal({title:'自定义封禁时长',editable:true,placeholderText:'请输入1-3650之间的天数',success:resolve}));const days=Number(custom.content);if(!custom.confirm||!Number.isInteger(days)||days<1||days>3650)return uni.showToast({title:'请输入正确天数',icon:'none'});options=['timed',days]}const reason=await new Promise(resolve=>uni.showModal({title:`限制 ${user.name}`,editable:true,placeholderText:'请填写原因',success:resolve}));if(!reason.confirm||!reason.content)return;await addRestriction(user.id,{level:options[0],days:options[1],reason:reason.content});uni.showToast({title:'限制已生效',icon:'success'});await load()}
async function revoke(id){await revokeRestriction(id);uni.showToast({title:'已解除',icon:'success'});await load()}
onShow(load)
</script>

<style scoped>
.page{padding:20rpx;background:#f5f6f8;min-height:100vh}.search{display:flex;gap:12rpx;margin-bottom:14rpx}.search input{flex:1;background:#fff;border-radius:12rpx;padding:0 20rpx;font-size:24rpx}.search button{margin:0;background:#1a6b47;color:#fff;font-size:23rpx}.rule-tip{padding:18rpx;background:#eef7f2;color:#315e49;border-radius:12rpx;margin-bottom:16rpx;font-size:22rpx;line-height:1.6}.card{display:flex;align-items:center;background:#fff;padding:24rpx;border-radius:16rpx;margin-bottom:12rpx}.main{flex:1;display:flex;flex-direction:column;gap:7rpx;font-size:22rpx;color:#87918c}.name{font-size:28rpx;font-weight:700;color:#293c33}.role{font-size:19rpx;padding:3rpx 8rpx;background:#edf2ef;border-radius:6rpx}.violations{color:#a45d16}.restriction{display:flex;justify-content:space-between;padding:10rpx;margin-top:6rpx;border-radius:8rpx;background:#fff0f0;color:#a94343}.revoke{text-decoration:underline;margin-left:12rpx}.restrict{margin:0 0 0 12rpx;font-size:21rpx;line-height:58rpx;background:#a94343;color:#fff}.empty{text-align:center;padding:100rpx;color:#999}
</style>
