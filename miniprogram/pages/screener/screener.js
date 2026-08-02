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
    page: 1,
    pageSize: 20,

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
  },

  onRemoveCondition(e) {
    const idx = e.detail.index;
    this.setData({
      conditions: this.data.conditions.filter((_, i) => i !== idx),
    });
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

    api.searchScreener({
      conditions: this.data.conditions,
      logic: this.data.logic,
      report_type: this.data.reportType,
      page: 1,
      page_size: this.data.pageSize,
    })
      .then((res) => {
        const d = res.data || {};
        this.setData({
          results: d.items || [],
          total: d.total || 0,
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

  onStockTap(e) {
    wx.navigateTo({ url: `/pages/stock/stock?symbol=${e.detail.symbol}` });
  },
});
