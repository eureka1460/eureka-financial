// app.js
App({
  onLaunch: function () {
    // 初始化云开发
    if (!wx.cloud) {
      console.error('请使用 2.2.3 或以上的基础库以使用云能力');
      return;
    }
    wx.cloud.init({
      env: 'cloud1-d2gaskev55a202518',
      traceUser: true,
    });

    // 全局数据
    this.globalData = {
      // 后端连接状态
      backendOnline: false,
      // 已选择的行业筛选
      activeIndustry: '',
    };
  },

  /** 检查后端连通性 */
  checkBackend() {
    const api = require('./utils/api');
    return api
      .get('/api/v1/health')
      .then(() => {
        this.globalData.backendOnline = true;
        return true;
      })
      .catch(() => {
        this.globalData.backendOnline = false;
        return false;
      });
  },
});
