<template>
  <view class="page">
    <view class="login-card">
      <image class="logo" src="/static/logo.png" mode="aspectFit" />
      <text class="title">笃学书院空间预约</text>

      <input class="input" v-model="studentId" placeholder="请输入学号" />
      <input class="input" v-model="password" type="password" placeholder="请输入密码" />

      <button class="btn-primary login-btn" @click="handleLogin" :loading="loading">登 录</button>

      <view class="link-row">
        <text class="link" @click="goRegister">没有账号？去注册</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { useUserStore } from '@/store/user.js'

const studentId = ref('')
const password = ref('')
const loading = ref(false)
const store = useUserStore()

async function handleLogin() {
  if (!studentId.value || !password.value) {
    uni.showToast({ title: '请填写学号和密码', icon: 'none' })
    return
  }
  loading.value = true
  try {
    await store.login(studentId.value, password.value)
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => uni.switchTab({ url: '/pages/index/index' }), 500)
  } catch { /* api layer shows toast */ }
  finally { loading.value = false }
}

function goRegister() {
  uni.navigateTo({ url: '/pages/register/register' })
}
</script>

<style scoped>
.page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(180deg, #F1EDFB 0%, #F6F7F9 60%);
}
.login-card {
  background: #fff;
  border-radius: 24rpx;
  padding: 60rpx 48rpx;
  width: 600rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  border: 1rpx solid #ECEEF2;
  box-shadow: 0 6rpx 24rpx rgba(23, 28, 36, 0.05);
}
.logo { width: 120rpx; height: 120rpx; margin-bottom: 16rpx; }
.title { font-size: 36rpx; font-weight: 700; color: #F25B15; margin-bottom: 40rpx; }
.input {
  width: 100%;
  border: 2rpx solid #ECEEF2;
  border-radius: 12rpx;
  padding: 24rpx 20rpx;
  margin-bottom: 24rpx;
  font-size: 28rpx;
  box-sizing: border-box;
  background: #F6F7F9;
}
.login-btn { width: 100%; margin-top: 16rpx; box-shadow: 0 5px 12px rgba(242,91,21,0.22); }
.link-row { margin-top: 32rpx; }
.link { color: #6B46C1; font-size: 26rpx; }
</style>
