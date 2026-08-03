import { defineStore } from 'pinia'
import { login as apiLogin, register as apiRegister, getMe } from '@/api/index.js'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null,
    token: null,
  }),

  getters: {
    isLoggedIn: (s) => !!s.token,
    isAdmin: (s) => s.user?.role === 'admin',
    isCounselor: (s) => s.user?.role === 'counselor' || s.user?.role === 'admin',
  },

  actions: {
    async login(studentId, password) {
      const res = await apiLogin({ student_id: studentId, password })
      this.token = res.access_token
      this.user = res.user
      uni.setStorageSync('token', this.token)
      return res
    },

    async register(data) {
      const res = await apiRegister(data)
      this.token = res.access_token
      this.user = res.user
      uni.setStorageSync('token', this.token)
      return res
    },

    async fetchUser() {
      try {
        this.user = await getMe()
      } catch {
        this.logout()
      }
    },

    logout() {
      this.user = null
      this.token = null
      uni.removeStorageSync('token')
      uni.reLaunch({ url: '/pages/login/login' })
    },
  },
})
