/**
 * 选股筛选页
 */
const api = require('../../utils/api');

Page({
  data: {
    conditions: [],
    logic: 'AND',
    reportType: 'annual',

    // 条件构建
    builderMetric: '',
    builderMetricName: '',
    builderOperator: '>=',
    builderValue: '',
    builderUnit: '',
    builderYears: 1,
    showMetricList: false,

    // 指标列表（有默认值，页面加载即能用）
    indicators: [
      { field: 'roe', chinese_name: '净资产收益率(ROE)', unit: '%', category: '盈利能力' },
      { field: 'roa', chinese_name: '总资产收益率(ROA)', unit: '%', category: '盈利能力' },
      { field: 'gross_margin', chinese_name: '毛利率', unit: '%', category: '盈利能力' },
      { field: 'net_margin', chinese_name: '净利率', unit: '%', category: '盈利能力' },
      { field: 'operating_margin', chinese_name: '营业利润率', unit: '%', category: '盈利能力' },
      { field: 'revenue_yoy', chinese_name: '营收同比增长率', unit: '%', category: '成长能力' },
      { field: 'net_profit_yoy', chinese_name: '利润同比增长率', unit: '%', category: '成长能力' },
      { field: 'debt_to_assets', chinese_name: '资产负债率', unit: '%', category: '偿债能力' },
      { field: 'current_ratio', chinese_name: '流动比率', unit: '倍', category: '偿债能力' },
      { field: 'quick_ratio', chinese_name: '速动比率', unit: '倍', category: '偿债能力' },
      { field: 'fcf', chinese_name: '自由现金流(FCF)', unit: '元', category: '估值相关' },
      { field: 'operating_revenue', chinese_name: '营业总收入', unit: '元', category: '利润表' },
      { field: 'net_profit_attr_parent', chinese_name: '归母净利润', unit: '元', category: '利润表' },
    ],
    indicatorNames: [
      '净资产收益率(ROE) (%)', '总资产收益率(ROA) (%)', '毛利率 (%)', '净利率 (%)', '营业利润率 (%)',
      '营收同比增长率 (%)', '利润同比增长率 (%)', '资产负债率 (%)', '流动比率 (倍)', '速动比率 (倍)',
      '自由现金流(FCF) (元)', '营业总收入 (元)', '归母净利润 (元)',
    ],

    // 结果
    results: [],
    total: 0,
    page: 0,
    pageSize: 20,
    hasMore: false,
    loadingMore: false,

    loading: false,
    searched: false,
    error: '',
  },

  onLoad() {
    this.loadIndicators();
  },

  // ── 指标列表 ──────────────────────────
  loadIndicators() {
    api.getIndicators()
      .then((res) => {
        let list = res.data || [];
        list = list.map((i) => {
          if (i.unit === '元') return { ...i, unit: '亿元' };
          return i;
        });
        this.setData({
          indicators: list,
          indicatorNames: list.map((i) => i.chinese_name + ' (' + i.unit + ')'),
        });
      })
      .catch(() => {
        const defaults = [
          { field: 'roe', chinese_name: '净资产收益率(ROE)', unit: '%', category: '盈利能力' },
          { field: 'roa', chinese_name: '总资产收益率(ROA)', unit: '%', category: '盈利能力' },
          { field: 'gross_margin', chinese_name: '毛利率', unit: '%', category: '盈利能力' },
          { field: 'net_margin', chinese_name: '净利率', unit: '%', category: '盈利能力' },
          { field: 'operating_margin', chinese_name: '营业利润率', unit: '%', category: '盈利能力' },
          { field: 'revenue_yoy', chinese_name: '营收同比增长率', unit: '%', category: '成长能力' },
          { field: 'net_profit_yoy', chinese_name: '归母净利润同比增长率', unit: '%', category: '成长能力' },
          { field: 'debt_to_assets', chinese_name: '资产负债率', unit: '%', category: '偿债能力' },
          { field: 'current_ratio', chinese_name: '流动比率', unit: '倍', category: '偿债能力' },
          { field: 'quick_ratio', chinese_name: '速动比率', unit: '倍', category: '偿债能力' },
          { field: 'fcf', chinese_name: '自由现金流(FCF)', unit: '亿元', category: '估值相关' },
          { field: 'operating_revenue', chinese_name: '营业总收入', unit: '亿元', category: '利润表' },
          { field: 'net_profit_attr_parent', chinese_name: '归母净利润', unit: '亿元', category: '利润表' },
        ];
        this.setData({
          indicators: defaults,
          indicatorNames: defaults.map((i) => i.chinese_name + ' (' + i.unit + ')'),
        });
      });
  },

  // ── 条件构建 ──────────────────────────
  onToggleMetricList() {
    this.setData({ showMetricList: !this.data.showMetricList });
  },

  onPickMetric(e) {
    const idx = e.currentTarget.dataset.idx;
    const item = this.data.indicators[idx];
    if (item) {
      this.setData({
        builderMetric: item.field,
        builderMetricName: item.chinese_name,
        builderUnit: item.unit || '',
        showMetricList: false,
      });
    }
  },

  onPickOperator(e) {
    this.setData({ builderOperator: e.currentTarget.dataset.op });
  },

  onValueInput(e) {
    this.setData({ builderValue: e.detail.value });
  },

  onYearsChange(e) {
    this.setData({ builderYears: parseInt(e.detail.value) || 1 });
  },

  onAddCondition() {
    const { builderMetric, builderMetricName, builderOperator, builderValue, builderYears } = this.data;
    if (!builderMetric) {
      wx.showToast({ title: '请选择指标', icon: 'none' });
      return;
    }
    if (builderValue === '' || isNaN(parseFloat(builderValue))) {
      wx.showToast({ title: '请输入有效数值', icon: 'none' });
      return;
    }

    // 亿元 → 元 自动转换
    let finalValue = parseFloat(builderValue);
    if (this.data.builderUnit === '亿元') {
      finalValue = finalValue * 1e8;
    }
    const conditions = [...this.data.conditions, {
      metric: builderMetric,
      operator: builderOperator,
      value: finalValue,
      consecutive_years: builderYears,
      _label: builderMetricName,
    }];

    this.setData({
      conditions,
      builderValue: '',
      builderMetric: '',
      builderMetricName: '',
      builderYears: 1,
    });
    this.resetResults();
  },

  onRemoveCondition(e) {
    const idx = e.detail.index;
    this.setData({
      conditions: this.data.conditions.filter((_, i) => i !== idx),
    });
    this.resetResults();
  },

  onToggleLogic() {
    this.setData({ logic: this.data.logic === 'AND' ? 'OR' : 'AND' });
    this.resetResults();
  },

  onPickReportType(e) {
    const reportType = e.currentTarget.dataset.type;
    if (reportType !== this.data.reportType) {
      this.setData({ reportType });
      this.resetResults();
    }
  },

  // ── 执行筛选 ──────────────────────────
  resetResults() {
    this._searchToken = (this._searchToken || 0) + 1;
    this._activeQuery = null;
    this.setData({
      results: [], total: 0, page: 0, hasMore: false,
      loading: false, loadingMore: false, searched: false, error: '',
    });
  },

  onSearch() {
    if (this.data.conditions.length === 0) {
      wx.showToast({ title: '请至少添加一个条件', icon: 'none' });
      return;
    }

    const token = (this._searchToken || 0) + 1;
    this._searchToken = token;
    this._activeQuery = {
      conditions: this.data.conditions.map(({ metric, operator, value, consecutive_years }) => ({
        metric, operator, value, consecutive_years,
      })),
      logic: this.data.logic,
      report_type: this.data.reportType,
      page_size: this.data.pageSize,
    };
    this.setData({
      loading: true, loadingMore: false, error: '', searched: true,
      results: [], total: 0, page: 0, hasMore: false,
    });
    this.loadPage(1, token);
  },

  loadPage(page, token) {
    if (!this._activeQuery || token !== this._searchToken) return;
    if (page > 1) this.setData({ loadingMore: true, error: '' });

    api.searchScreener({ ...this._activeQuery, page })
      .then((res) => {
        if (token !== this._searchToken) return;
        const d = res.data || {};
        const items = Array.isArray(d.items) ? d.items : [];
        const total = Number(d.total) || 0;
        const results = page === 1 ? items : this.data.results.concat(items);
        this.setData({
          results,
          total,
          page,
          hasMore: items.length > 0 && results.length < total,
          loading: false,
          loadingMore: false,
        });
      })
      .catch((err) => {
        if (token !== this._searchToken) return;
        this.setData({
          loading: false,
          loadingMore: false,
          error: err.message || '筛选失败',
        });
      });
  },

  onReachBottom() {
    this.onLoadMore();
  },

  onLoadMore() {
    if (this.data.loading || this.data.loadingMore || !this.data.hasMore) return;
    this.loadPage(this.data.page + 1, this._searchToken);
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
