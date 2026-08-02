/**
 * 股票详情页：基本信息 + 财务指标 + 历史报表
 */
const api = require('../../utils/api');
const { fmtPercent, fmtAmount, fmtDate, fmtReportType } = require('../../utils/format');

Page({
  data: {
    symbol: '',
    stock: null,
    financial: null,
    loading: true,
    error: '',
    revenueYoYClass: '',
    profitYoYClass: '',

    // 财务历史
    history: [],
    historyReportType: '',
    historyYears: 5,
    historyLoading: false,
    historyError: '',

    // 图表数据
    chartRevenue: [],
    chartProfit: [],
    chartROE: [],
    showCharts: false,

    // 点击指标弹出图表
    chartMetricName: '',
    chartMetricData: [],

    // 指标展示
    roe: '--',
    roa: '--',
    grossMargin: '--',
    netMargin: '--',
    operatingMargin: '--',
    revenueYoY: '--',
    profitYoY: '--',
    currentRatio: '--',
    quickRatio: '--',
    debtToAssets: '--',
    fcf: '--',
    bookValuePerShare: '--',
    totalAssets: '--',
    totalEquity: '--',
    operatingRevenue: '--',
    netProfit: '--',
  },

  onLoad(options) {
    const symbol = options.symbol || '';
    this.setData({ symbol });
    if (symbol) {
      this.loadDetail();
      this.loadHistory();
      this.loadChartData();
    }
  },

  // ── 股票详情 ──────────────────────────
  loadDetail() {
    this.setData({ loading: true });
    api.getStockDetail(this.data.symbol)
      .then((res) => {
        const stock = res.data;
        const fin = stock.latest_financial || {};

        const navTitle = stock.name ? `${stock.name} (${stock.symbol})` : stock.symbol;
        wx.setNavigationBarTitle({ title: navTitle });

        this.setData({
          stock,
          financial: fin,
          loading: false,
          roe: fmtPercent(fin.roe),
          roa: fmtPercent(fin.roa),
          grossMargin: fmtPercent(fin.gross_margin),
          netMargin: fmtPercent(fin.net_margin),
          operatingMargin: fmtPercent(fin.operating_margin),
          revenueYoY: fmtPercent(fin.revenue_yoy),
          profitYoY: fmtPercent(fin.net_profit_yoy),
          revenueYoYClass: fin.revenue_yoy != null ? (fin.revenue_yoy >= 0 ? 'text-up' : 'text-down') : '',
          profitYoYClass: fin.net_profit_yoy != null ? (fin.net_profit_yoy >= 0 ? 'text-up' : 'text-down') : '',
          currentRatio: fmtPercent(fin.current_ratio),
          quickRatio: fmtPercent(fin.quick_ratio),
          debtToAssets: fmtPercent(fin.debt_to_assets),
          fcf: fmtAmount(fin.fcf),
          bookValuePerShare: fin.book_value_per_share != null ? Number(fin.book_value_per_share).toFixed(2) + '元' : '--',
          totalAssets: fmtAmount(fin.total_assets),
          totalEquity: fmtAmount(fin.total_equity),
          operatingRevenue: fmtAmount(fin.operating_revenue),
          netProfit: fmtAmount(fin.net_profit_attr_parent),
        });
      })
      .catch((err) => {
        this.setData({ loading: false, error: err.message || '加载失败' });
      });
  },

  // ── 财务历史 ──────────────────────────
  loadHistory() {
    this.setData({ historyLoading: true });
    const params = { years: this.data.historyYears };
    if (this.data.historyReportType) {
      params.report_type = this.data.historyReportType;
    }

    api.getFinancials(this.data.symbol, params)
      .then((res) => {
        const items = (res.data || []).map((item) => ({
          ...item,
          _date: fmtDate(item.report_date),
          _type: fmtReportType(item.report_type),
          _revenue: fmtAmount(item.operating_revenue),
          _profit: fmtAmount(item.net_profit_attr_parent),
          _eps: item.basic_eps ? Number(item.basic_eps).toFixed(2) : '--',
          _roe: fmtPercent(item.roe),
          _margin: fmtPercent(item.gross_margin),
        }));
        this.setData({ history: items, historyLoading: false });
      })
      .catch((err) => {
        this.setData({ historyLoading: false, historyError: '加载历史数据失败' });
        console.error('加载财务历史失败:', err);
      });
  },

  onHistoryTypeChange(e) {
    const type = e.currentTarget.dataset.type;
    this.setData({ historyReportType: type });
    this.loadHistory();
  },

  // ── 跳转 ──────────────────────────────
  goValuation() {
    wx.navigateTo({
      url: `/pages/valuation/valuation?symbol=${this.data.symbol}`,
    });
  },

  goScreener() {
    wx.switchTab({ url: '/pages/screener/screener' });
  },

  // ── 图表数据 ──────────────────────────
  loadChartData() {
    api.getFinancials(this.data.symbol, { report_type: 'annual', years: 5 })
      .then((res) => {
        const items = (res.data || []).reverse(); // 按年份升序
        this.setData({
          chartRevenue: items.map((r) => ({ year: r.fiscal_year, value: r.operating_revenue, yoy: r.revenue_yoy, label: '营收' })),
          chartProfit: items.map((r) => ({ year: r.fiscal_year, value: r.net_profit_attr_parent, yoy: r.net_profit_yoy, label: '利润' })),
          chartROE: items.map((r) => ({ year: r.fiscal_year, value: r.roe, yoy: null, label: 'ROE' })),
        });
      })
      .catch(() => {});
  },

  onToggleCharts() {
    this.setData({ showCharts: !this.data.showCharts });
  },

  // 点击指标查看历年图表
  onTapMetric(e) {
    // 兼容两种事件来源：组件 tapmetric 事件 (e.detail) 和普通 bindtap (e.currentTarget.dataset)
    const field = e.detail?.field || e.currentTarget.dataset.field;
    const name = e.detail?.name || e.currentTarget.dataset.name;
    if (!field) return;

    // YoY 字段映射：指标字段 → 对应的同比增长字段
    const yoyMap = {
      operating_revenue: 'revenue_yoy',
      net_profit_attr_parent: 'net_profit_yoy',
      operating_profit: 'operating_profit_yoy',
    };

    api.getFinancials(this.data.symbol, { report_type: 'annual', years: 5 })
      .then((res) => {
        const items = (res.data || []).reverse();
        const yoyField = yoyMap[field] || null;
        const data = items.map((r) => ({
          year: r.fiscal_year,
          value: r[field] != null ? Number(r[field]) : 0,
          yoy: yoyField ? (r[yoyField] != null ? Number(r[yoyField]) : null) : null,
          label: name,
        }));
        this.setData({ chartMetricName: name, chartMetricData: data });
      })
      .catch(() => {});
  },

  onHideMetricChart() {
    this.setData({ chartMetricName: '', chartMetricData: [] });
  },

  onRetry() {
    this.loadDetail();
    this.loadHistory();
    this.loadChartData();
  },
});
