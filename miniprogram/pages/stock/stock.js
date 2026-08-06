/**
 * 股票详情页 — 多期数据对比表 + 指标图表
 */
const api = require('../../utils/api');
const { fmtPercent, fmtAmount } = require('../../utils/format');

// 指标定义
const METRICS = [
  { field: 'operating_revenue', name: '营业总收入', unit: '元', isAmount: true },
  { field: 'net_profit_attr_parent', name: '归母净利润', unit: '元', isAmount: true },
  { field: 'roe', name: 'ROE', unit: '%', isRatio: true },
  { field: 'roa', name: 'ROA', unit: '%', isRatio: true },
  { field: 'gross_margin', name: '毛利率', unit: '%', isRatio: true },
  { field: 'net_margin', name: '净利率', unit: '%', isRatio: true },
  { field: 'operating_margin', name: '营业利润率', unit: '%', isRatio: true },
  { field: 'revenue_yoy', name: '营收同比增长', unit: '%', isRatio: true },
  { field: 'net_profit_yoy', name: '净利同比增长', unit: '%', isRatio: true },
  { field: 'current_ratio', name: '流动比率', unit: '倍', isRatio: true },
  { field: 'quick_ratio', name: '速动比率', unit: '倍', isRatio: true },
  { field: 'debt_to_assets', name: '资产负债率', unit: '%', isRatio: true },
  { field: 'fcf', name: '自由现金流', unit: '元', isAmount: true },
  { field: 'book_value_per_share', name: '每股净资产', unit: '元', isRatio: true },
  { field: 'basic_eps', name: '基本每股收益', unit: '元', isRatio: true },
  { field: 'total_assets', name: '总资产', unit: '元', isAmount: true },
  { field: 'total_equity', name: '净资产', unit: '元', isAmount: true },
];

// 帮助文本
const HELP = {
  'ROE': '净利润 / 平均净资产。15%以上为优秀。',
  'ROA': '净利润 / 平均总资产。越高越好。',
  '毛利率': '（营收 − 营业成本）/ 营收。反映产品竞争力。',
  '净利率': '归母净利润 / 营收。',
  '营业利润率': '营业利润 / 营收。只看主业。',
  '营收同比增长': '（本期 − 上年同期）/ 上年同期。',
  '净利同比增长': '（本期净利 − 上年同期）/ 上年同期。',
  '流动比率': '流动资产 / 流动负债。>2 安全。',
  '速动比率': '（现金+交易性金融资产+应收款）/ 流动负债。',
  '资产负债率': '总负债 / 总资产。40-60% 适中。',
  '自由现金流': '经营现金流 − 资本支出。可自由支配的钱。',
  '每股净资产': '股东权益 / 总股本。账面价值。',
  '基本每股收益': '归母净利润 / 总股本。每股赚多少。',
  '营业总收入': '主营业务收入+其他业务收入。顶行收入。',
  '归母净利润': '归属母公司股东的净利润。',
  '总资产': '公司拥有的全部资源。',
  '净资产': '总资产 − 总负债。股东权益。',
};

Page({
  data: {
    symbol: '',
    stock: null,
    loading: true,
    error: '',

    // 头部
    marketLabel: '',

    // 对比表
    periods: [],
    rows: [],

    // 图表
    showCharts: false,
    chartRevenue: [], chartProfit: [], chartROE: [],

    // 点击指标图表
    chartMetricName: '',
    chartMetricData: [],

    // 帮助
    helpName: '',
    helpText: '',
  },

  onLoad(options) {
    const symbol = options.symbol || '';
    this.setData({ symbol });
    if (symbol) this.loadAll();
  },

  // ── 加载全部数据 ──────────────────────
  async loadAll() {
    this.setData({ loading: true });
    try {
      const [detailRes, finRes] = await Promise.all([
        api.getStockDetail(this.data.symbol),
        api.getFinancials(this.data.symbol, { years: 3 }),
      ]);

      const stock = detailRes.data;
      const allData = finRes.data || [];

      // 头部
      const mktMap = { SH: '沪市', SZ: '深市', BJ: '北交所' };
      this.setData({
        stock,
        marketLabel: mktMap[stock.market] || stock.market || '',
      });

      // 构建对比表
      this.buildTable(allData);

      // 图表数据
      this.buildCharts(allData);
    } catch (e) {
      this.setData({ error: e.message || '加载失败' });
    }
    this.setData({ loading: false });
  },

  // ── 构建多期对比表 ──────────────────
  buildTable(allData) {
    // 取最近 4 条不同时期的数据
    const periods = [];
    const seen = new Set();
    for (const r of allData) {
      const key = r.report_date + '_' + r.report_type;
      if (!seen.has(key) && periods.length < 4) {
        seen.add(key);
        const typeMap = { annual: '年报', q1: '一季报', semi_annual: '中报', q3: '三季报' };
        periods.push({
          key,
          date: r.report_date,
          type: r.report_type,
          fy: r.fiscal_year,
          label: r.fiscal_year + typeMap[r.report_type] || r.report_type,
          data: r,
        });
      }
    }

    // 构建每行指标
    const rows = METRICS.map((m) => {
      const vals = periods.map((p) => {
        const v = p.data[m.field];
        let text = '--';
        let cls = '';
        if (v != null) {
          if (m.isAmount) {
            text = fmtAmount(v);
          } else if (m.isRatio && m.unit === '%') {
            text = fmtPercent(v);
          } else {
            text = Number(v).toFixed(2);
          }
          // 同比类着色
          if (m.field.includes('yoy') && v !== null) {
            cls = v >= 0 ? 'text-up' : 'text-down';
          }
        }
        return { text, cls };
      });
      return { ...m, vals };
    });

    this.setData({ periods, rows });
  },

  // ── 图表数据 ────────────────────────
  buildCharts(allData) {
    const annuals = allData.filter((r) => r.report_type === 'annual').reverse();
    this.setData({
      chartRevenue: annuals.map((r) => ({
        year: r.fiscal_year, value: r.operating_revenue,
        yoy: r.revenue_yoy,
      })),
      chartProfit: annuals.map((r) => ({
        year: r.fiscal_year, value: r.net_profit_attr_parent,
        yoy: r.net_profit_yoy,
      })),
      chartROE: annuals.map((r) => ({
        year: r.fiscal_year, value: r.roe, yoy: null,
      })),
    });
  },

  onToggleCharts() {
    this.setData({ showCharts: !this.data.showCharts });
  },

  // ── 点击指标 → 图表 ─────────────────
  onTapMetric(e) {
    const field = e.currentTarget.dataset.field;
    const name = e.currentTarget.dataset.name;
    api.getFinancials(this.data.symbol, { report_type: 'annual', years: 5 }).then((res) => {
      const items = (res.data || []).reverse();
      const data = items.map((r, i) => {
        const val = r[field] != null ? Number(r[field]) : 0;
        let yoy = null;
        if (i > 0 && items[i - 1][field] != null && items[i - 1][field] !== 0) {
          const prev = Number(items[i - 1][field]);
          yoy = prev !== 0 ? (val - prev) / Math.abs(prev) : null;
        }
        return { year: r.fiscal_year, value: val, yoy };
      });
      this.setData({ chartMetricName: name, chartMetricData: data });
    });
  },

  onHideMetricChart() {
    this.setData({ chartMetricName: '', chartMetricData: [] });
  },

  // ── 帮助弹窗 ───────────────────────
  onHelpTap(e) {
    const name = e.currentTarget.dataset.name;
    this.setData({ helpName: name, helpText: HELP[name] || '暂无说明' });
  },
  onCloseHelp() {
    this.setData({ helpText: '' });
  },

  onRetry() { this.loadAll(); },
});
