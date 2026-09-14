/**
 * 首页：股票列表 + 搜索 + 行业筛选
 */
const api = require('../../utils/api');

Page({
  data: {
    keyword: '',
    searchInput: '',
    industries: [],
    activeIndustry: '',
    stocks: [],
    page: 1,
    pageSize: 20,
    total: 0,
    hasMore: true,
    loading: false,
    initialLoading: true,
    error: '',
  },

  onLoad() {
    this.loadIndustries();
    this.loadStocks(true);
  },

  onPullDownRefresh() {
    this.setData({ page: 1, hasMore: true });
    this.loadStocks(true, () => wx.stopPullDownRefresh());
  },

  onReachBottom() {
    if (this.data.hasMore && !this.data.loading) {
      this.loadStocks(false);
    }
  },

  loadIndustries() {
    const industries = [
      '食品饮料', '医药生物', '电子', '计算机', '电力设备',
      '汽车', '机械设备', '化工', '有色金属', '银行',
      '非银金融', '房地产', '建筑装饰', '交通运输', '公用事业',
    ];
    this.setData({ industries });
  },

  loadStocks(reset = false, callback = null) {
    this.setData({ loading: true, error: '' });

    const params = {
      page: reset ? 1 : this.data.page + 1,
      page_size: this.data.pageSize,
    };
    if (this.data.keyword) params.keyword = this.data.keyword;
    if (this.data.activeIndustry) params.industry = this.data.activeIndustry;

    api.getStocks(params)
      .then((res) => {
        const d = res.data;
        const items = (d && d.items) ? d.items : [];
        const newStocks = reset ? items : [...this.data.stocks, ...items];
        const total = (d && d.total) || 0;

        this.setData({
          stocks: newStocks,
          page: reset ? 1 : this.data.page + 1,
          total,
          hasMore: newStocks.length < total,
          loading: false,
          initialLoading: false,
        });
        if (callback) callback();
      })
      .catch((err) => {
        console.error('加载股票列表失败:', err);
        this.setData({
          loading: false,
          initialLoading: false,
          error: err.message || '加载失败',
        });
        if (callback) callback();
      });
  },

  onSearchInput(e) {
    this.setData({ searchInput: e.detail.value });
  },

  onSearchConfirm(e) {
    const kw = (e.detail.value || '').trim();
    this.setData({ keyword: kw, page: 1, hasMore: true });
    this.loadStocks(true);
  },

  onClearSearch() {
    this.setData({ keyword: '', searchInput: '', page: 1, hasMore: true });
    this.loadStocks(true);
  },

  onIndustryTap(e) {
    const industry = e.currentTarget.dataset.industry;
    const active = this.data.activeIndustry === industry ? '' : industry;
    this.setData({ activeIndustry: active, page: 1, hasMore: true });
    this.loadStocks(true);
  },

  onStockTap(e) {
    const symbol = String((e.detail && e.detail.symbol) || '').trim();
    if (!symbol || symbol === 'undefined' || symbol === 'null') {
      wx.showToast({ title: '股票代码无效', icon: 'none' });
      return;
    }
    wx.navigateTo({
      url: `/pages/stock/stock?symbol=${encodeURIComponent(symbol)}`,
    });
  },
});
