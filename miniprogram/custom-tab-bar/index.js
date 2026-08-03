Component({
  data: {
    selected: 0,
    list: [
      { pagePath: '/pages/index/index', text: '空间导览', icon: 'grid' },
      { pagePath: '/pages/my/my', text: '我的', icon: 'person' }
    ]
  },

  lifetimes: {
    attached() {
      const saved = wx.getStorageSync('_tab')
      if (saved != null) this.setData({ selected: saved })
    }
  },

  methods: {
    switch(e) {
      const { path, index } = e.currentTarget.dataset
      if (index === this.data.selected) return
      this.setData({ selected: index })
      wx.setStorageSync('_tab', index)
      wx.switchTab({ url: path })
    }
  }
})
