<template>
  <view class="page">
    <view class="card">
      <text class="title">注册账号</text>

      <input class="input" v-model="form.student_id" placeholder="学号（数字）" />
      <input class="input" v-model="form.name" placeholder="姓名" />
      <input class="input" v-model="form.phone" placeholder="手机号" type="number" maxlength="11" />
      <input class="input" v-model="form.class_name" placeholder="班级（如：计科2201）" />
      <input class="input" v-model="form.password" type="password" placeholder="密码（至少6位）" />
      <input class="input" v-model="form.password2" type="password" placeholder="确认密码" />

      <button class="btn-primary login-btn" @click="handleRegister" :loading="loading">注 册</button>

      <view class="link-row">
        <text class="link" @click="goLogin">已有账号？去登录</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useUserStore } from '@/store/user.js'

const form = reactive({
  student_id: '', name: '', phone: '', class_name: '', password: '', password2: '',
})
const loading = ref(false)
const store = useUserStore()

async function handleRegister() {
  if (!form.student_id || !form.name || !form.phone || !form.class_name || !form.password) {
    uni.showToast({ title: '请填写所有字段', icon: 'none' })
    return
  }
  if (form.password !== form.password2) {
    uni.showToast({ title: '两次密码不一致', icon: 'none' })
    return
  }
  if (form.password.length < 6) {
    uni.showToast({ title: '密码至少6位', icon: 'none' })
    return
  }
  loading.value = true
  try {
    await store.register({
      student_id: form.student_id,
      name: form.name,
      phone: form.phone,
      class_name: form.class_name,
      password: form.password,
    })
    uni.showToast({ title: '注册成功', icon: 'success' })
    setTimeout(() => uni.switchTab({ url: '/pages/index/index' }), 500)
  } catch { /* api layer shows toast */ }
  finally { loading.value = false }
}

function goLogin() {
  uni.navigateBack()
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f5f5f5;
  padding: 40rpx 0;
}
.title { font-size: 36rpx; font-weight: 700; color: #1a5c3a; display: block; text-align: center; margin-bottom: 40rpx; }
.input {
  width: 100%;
  border: 2rpx solid #ddd;
  border-radius: 12rpx;
  padding: 24rpx 20rpx;
  margin-bottom: 20rpx;
  font-size: 28rpx;
  box-sizing: border-box;
}
.login-btn { width: 100%; margin-top: 16rpx; }
.link-row { margin-top: 32rpx; text-align: center; }
.link { color: #1a5c3a; font-size: 26rpx; }
</style>
