/**
 * 选股筛选页
 */
const api = require('../../utils/api');

// 指标元数据缓存
let indicatorsCache = [];

Page({
  data: {
    // 条件构建
    conditions: [],
    logic: 'AND',
    reportType: 'annual',

    // 添加条件面板
    showBuilder: false,
    builderMetric: '',
    builderOperator: '>=',
    builderValue: '',
    builderYears: 1,
    indicators: [],

    // 结果
    results: [],
    total: 0,
    page: 1,
    pageSize: 20,

    // 状态
    loading: false,
    searched: false,
    error: '',
  },

  onLoad() {
    this.loadIndicators();
  },

  // ── 指标列表 ──────────────────────────
  loadIndicators() {
    if (indicatorsCache.length > 0) {
      this.setData({ indicators: indicatorsCache });
      return;
    }
    api.getIndicators()
      .then((res) => {
        indicatorsCache = res.data || [];
        this.setData({ indicators: indicatorsCache });
      })
      .catch(() => {
        // 使用默认指标
        const defaults = [
          { field: 'roe', chinese_name: '净资产收益率(ROE)', unit: '%', category: '盈利能力' },
          { field: 'gross_margin', chinese_name: '毛利率', unit: '%', category: '盈利能力' },
          { field: 'net_margin', chinese_name: '净利率', unit: '%', category: '盈利能力' },
          { field: 'revenue_yoy', chinese_name: '营收同比增长率', unit: '%', category: '成长能力' },
          { field: 'net_profit_yoy', chinese_name: '归母净利润同比增长率', unit: '%', category: '成长能力' },
          { field: 'debt_to_assets', chinese_name: '资产负债率', unit: '%', category: '偿债能力' },
          { field: 'current_ratio', chinese_name: '流动比率', unit: '倍', category: '偿债能力' },
          { field: 'fcf', chinese_name: '自由现金流(FCF)', unit: '元', category: '估值相关' },
        ];
        indicatorsCache = defaults;
        this.setData({ indicators: defaults });
      });
  },

  // ── 条件构建 ──────────────────────────
  onShowBuilder() {
    this.setData({ showBuilder: true });
  },

  onHideBuilder() {
    this.setData({ showBuilder: false });
  },

  onPickMetric(e) {
    const idx = e.currentTarget.dataset.index;
    const item = this.data.indicators[idx];
    this.setData({ builderMetric: item.field });
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
    const { builderMetric, builderOperator, builderValue, builderYears } = this.data;
    if (!builderMetric || builderValue === '') {
      wx.showToast({ title: '请完善条件', icon: 'none' });
      return;
    }

    const cond = {
      metric: builderMetric,
      operator: builderOperator,
      value: parseFloat(builderValue),
      consecutive_years: builderYears,
      _label: this.getMetricLabel(builderMetric),
    };

    const conditions = [...this.data.conditions, cond];
    this.setData({
      conditions,
      showBuilder: false,
      builderValue: '',
      builderMetric: '',
      builderYears: 1,
    });
  },

  onRemoveCondition(e) {
    const idx = e.detail.index;
    const conditions = this.data.conditions.filter((_, i) => i !== idx);
    this.setData({ conditions });
  },

  onToggleLogic() {
    this.setData({ logic: this.data.logic === 'AND' ? 'OR' : 'AND' });
  },

  onPickReportType(e) {
    this.setData({ reportType: e.currentTarget.dataset.type });
  },

  // ── 执行筛选 ──────────────────────────
  onSearch() {
    if (this.data.conditions.length === 0) {
      wx.showToast({ title: '请至少添加一个条件', icon: 'none' });
      return;
    }

    this.setData({ loading: true, error: '', searched: true });

    const request = {
      conditions: this.data.conditions,
      logic: this.data.logic,
      report_type: this.data.reportType,
      page: 1,
      page_size: this.data.pageSize,
    };

    api.searchScreener(request)
      .then((res) => {
        const d = res.data || {};
        this.setData({
          results: d.items || [],
          total: d.total || 0,
          page: 1,
          loading: false,
        });
      })
      .catch((err) => {
        this.setData({
          loading: false,
          error: err.message || '筛选失败',
          results: [],
        });
      });
  },

  // ── 跳转 ──────────────────────────────
  onStockTap(e) {
    const symbol = e.detail.symbol;
    wx.navigateTo({
      url: `/pages/stock/stock?symbol=${symbol}`,
    });
  },

  // ── 获取指标中文名 ────────────────
  getMetricLabel(field) {
    const found = this.data.indicators.find((i) => i.field === field);
    return found ? found.chinese_name : field;
  },
});
