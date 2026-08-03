<script>
export default {
  setup() {
    const token = uni.getStorageSync('token')
    if (!token) {
      const pages = getCurrentPages()
      const currentPage = pages[pages.length - 1]
      const noAuthPages = ['pages/login/login', 'pages/register/register']
      if (currentPage && !noAuthPages.includes(currentPage.route)) {
        uni.reLaunch({ url: '/pages/login/login' })
      }
    }
  },
}
</script>

<style>
page {
  background-color: #f5f5f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.status-free { color: #4caf50; }
.status-busy { color: #ff9800; }
.status-crowded { color: #f44336; }
.status-active { color: #2196f3; }
.status-checked_in { color: #4caf50; }
.status-missed { color: #f44336; }
.status-cancelled { color: #999; }

.btn-primary {
  background-color: #1a5c3a;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  padding: 20rpx 40rpx;
  font-size: 30rpx;
}
.btn-primary:active { opacity: 0.8; }

.btn-danger {
  background-color: #f44336;
  color: #fff;
  border: none;
  border-radius: 8rpx;
  padding: 20rpx 40rpx;
  font-size: 30rpx;
}

.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin: 20rpx;
  box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.06);
}
</style>
