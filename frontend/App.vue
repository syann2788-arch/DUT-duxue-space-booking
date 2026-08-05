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
  background-color: #F6F7F9;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.status-free { color: #0E9868; }
.status-busy { color: #F25B15; }
.status-crowded { color: #f44336; }
.status-active { color: #2196f3; }
.status-checked_in { color: #0E9868; }
.status-missed { color: #f44336; }
.status-cancelled { color: #999; }

.btn-primary {
  background-color: #F25B15;
  color: #fff;
  border: none;
  border-radius: 9999rpx;
  padding: 20rpx 40rpx;
  font-size: 30rpx;
  font-weight: 600;
}
.btn-primary:active { opacity: 0.85; }

.btn-danger {
  background-color: #f44336;
  color: #fff;
  border: none;
  border-radius: 9999rpx;
  padding: 20rpx 40rpx;
  font-size: 30rpx;
}

.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin: 20rpx;
  border: 1rpx solid #ECEEF2;
  box-shadow: 0 6rpx 24rpx rgba(23, 28, 36, 0.05);
}
</style>
