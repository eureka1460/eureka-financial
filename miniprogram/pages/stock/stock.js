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
    tableYears: 3,
    allDataCache: [],

    // 图表
    showCharts: false,
    chartRevenue: [], chartProfit: [], chartROE: [],

    // 点击指标图表
    chartMetricName: '',
    chartMetricData: [],
    chartBars: [],
    chartColW: 75,
    chartMinW: 500,
    chartDots: [],
    chartLines: [],
    chartField: '',
    tooltip: null,
    yLabels: [],
    yLabelsR: [],
    chartPeriod: 'annual',
    annualData: [],
    quarterlyData: [],

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
  loadAll() {
    this.setData({ loading: true });
    const that = this;
    api.getStockDetail(this.data.symbol).then(detailRes => {
      const stock = detailRes.data;
      api.getFinancials(this.data.symbol, { years: 5 }).then(finRes => {
        const allData = finRes.data || [];
        const mktMap = { SH: '沪市', SZ: '深市', BJ: '北交所' };

        // 年报缓存：每年的全年累计值（四个季度相加）
        const annualCache = {};
        for (const r of allData) {
          const fy = r.fiscal_year;
          if (!annualCache[fy]) {
            // 深拷贝基准行
            annualCache[fy] = JSON.parse(JSON.stringify(r));
            annualCache[fy].report_type = 'annual';
          } else {
            // 累加数值字段
            for (const k of Object.keys(r)) {
              if (typeof r[k] === 'number' && !['fiscal_year','id'].includes(k)) {
                annualCache[fy][k] = (annualCache[fy][k] || 0) + r[k];
              }
            }
          }
        }
        const annualData = Object.values(annualCache)
          .sort((a, b) => a.fiscal_year - b.fiscal_year);

        // 季报缓存：单季值，sort by date
        const quarterlyData = allData
          .filter(r => r.report_type !== 'annual')
          .sort((a, b) => (a.report_date || '').localeCompare(b.report_date || ''));

        that.setData({
          stock,
          marketLabel: mktMap[stock.market] || stock.market || '',
          annualData,
          quarterlyData,
          loading: false,
        });
        that.setData({ allDataCache: allData });
        that.buildTable();
        that.buildCharts(allData);
      }).catch(e => that.setData({ error: e.message || '加载失败', loading: false }));
    }).catch(e => that.setData({ error: e.message || '加载失败', loading: false }));
  },

  onFilterYears(e) {
    const y = parseInt(e.currentTarget.dataset.y);
    this.setData({ tableYears: y });
    this.buildTable();
  },

  // ── 构建多期对比表（累计值：把前面季度加回来）──
  buildTable() {
    const allData = this.data.allDataCache;
    const yrs = this.data.tableYears;
    const now = new Date().getFullYear();
    const minYear = now - yrs;
    const typeMap = { annual: '年报', q1: '一季报', semi_annual: '中报', q3: '三季报' };
    const order = ['q1', 'semi_annual', 'q3', 'annual'];

    // 收集所有时期
    const allPeriods = [];
    const seen = new Set();
    for (const r of allData) {
      if (r.fiscal_year < minYear) continue;
      const key = r.fiscal_year + '_' + r.report_type;
      if (seen.has(key)) continue;
      seen.add(key);
      allPeriods.push({ ...r });
    }

    // 按财年+报告顺序排序，计算累计值
    allPeriods.sort((a, b) => {
      if (a.fiscal_year !== b.fiscal_year) return a.fiscal_year - b.fiscal_year;
      return order.indexOf(a.report_type) - order.indexOf(b.report_type);
    });

    // 同财年内，每期累加前面的值
    for (let i = 1; i < allPeriods.length; i++) {
      if (allPeriods[i].fiscal_year === allPeriods[i - 1].fiscal_year) {
        for (const key of Object.keys(allPeriods[i])) {
          if (typeof allPeriods[i][key] === 'number' && key !== 'fiscal_year') {
            allPeriods[i][key] = (allPeriods[i][key] || 0) + (allPeriods[i - 1][key] || 0);
          }
        }
      }
    }

    // 取最近 8 期
    const periods = allPeriods.slice(-8).reverse().map(r => ({
      key: r.fiscal_year + '_' + r.report_type,
      date: r.report_date, type: r.report_type, fy: r.fiscal_year,
      label: r.fiscal_year + (typeMap[r.report_type] || r.report_type),
      data: r,
    }));

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
    this.showChart(field, name, this.data.chartPeriod);
  },

  onBarTap(e) {
    const idx = e.currentTarget.dataset.idx;
    const bar = this.data.chartBars[idx];
    if (!bar) return;
    // 关闭
    if (this.data.tooltip && this.data.tooltip.idx === idx) {
      this.setData({ tooltip: null });
      return;
    }
    const x = ((idx + 0.5) / this.data.chartBars.length) * 100;
    this.setData({
      tooltip: {
        idx, x,
        txt: bar._lbl + '\n绝对值：' + bar._val + '\n同比：' + (bar._yTxt || '--'),
      },
    });
  },

  onToggleChartPeriod() {
    const next = this.data.chartPeriod === 'annual' ? 'quarterly' : 'annual';
    this.setData({ chartPeriod: next });
    const m = this.data.rows.find(r => r.field === this.data.chartField);
    if (m) this.showChart(m.field, m.name, next);
  },

  showChart(field, name, period) {
    let source = period === 'annual'
      ? this.data.annualData
      : this.data.quarterlyData;

    // 数据已是单季值，无需减值

    if (source.length > 12) source = source.slice(-12);

    const vals = source.map(r => Math.abs(r[field] != null ? Number(r[field]) : 0));
    const max = Math.max(...vals, 1);

    const barMax = 200;
    const axisMax = max * 1.25;
    const yLabels = [this._fmtAmount(axisMax), this._fmtAmount(axisMax*0.75), this._fmtAmount(axisMax*0.5), this._fmtAmount(axisMax*0.25), '0'];
    const yLabelsR = period === 'annual' ? yLabels.map(() => '') : ['+50%','+25%','0%','-25%','-50%'];

    const bars = source.map((r, i) => {
      const v = r[field] != null ? Number(r[field]) : 0;
      let yoy = null;
      if (period === 'quarterly') {
        const thisQ = r.report_date;
        const prevYear = source.find(s => s.report_date === thisQ.replace(/^\d{4}/, m => String(Number(m) - 1)));
        if (prevYear && prevYear[field] != null && prevYear[field] !== 0) {
          yoy = (v - Number(prevYear[field])) / Math.abs(Number(prevYear[field]));
        }
      } else if (i > 0 && source[i - 1][field] != null && source[i - 1][field] !== 0) {
        const prev = Number(source[i - 1][field]);
        yoy = prev !== 0 ? (v - prev) / Math.abs(prev) : null;
      }
      return {
        year: period === 'annual' ? r.fiscal_year : (r.report_date || '').substring(0, 7),
        _h: Math.max(Math.round((Math.abs(v) / axisMax) * barMax), 4),
        _neg: v < 0,
        _val: this._fmtAmount(v),
        _lbl: period === 'annual' ? r.fiscal_year : (r.report_date || '').substring(0, 7),
        _yTxt: yoy != null ? (yoy >= 0 ? '+' : '') + (yoy * 100).toFixed(1) + '%' : '',
        _yDn: yoy != null && yoy < 0,
        _yNone: yoy == null,
      };
    });

    // 折线：计算连线位置
    const yVals = bars.map(b => b._yTxt !== '' ? parseFloat(b._yTxt) : null);
    const yAbs = yVals.filter(y => y != null).map(Math.abs);
    const yMax = yAbs.length > 0 ? Math.max(...yAbs, 0.1) : 1;
    const dotTop = 48; // 标签区高度
    const lineH = 160; // 折线可用高度
    const dots = bars.map((b, i) => {
      const y = yVals[i];
      if (y == null) return null;
      // 映射：y正值在上（top小），y负值在下（top大）
      const ratio = y / yMax;
      const top = dotTop + lineH / 2 - (ratio * lineH / 2);
      return { x: (i + 0.5) / bars.length * 100, y: (top / 290) * 100, val: y };
    });

    const lines = [];
    for (let i = 0; i < dots.length - 1; i++) {
      const a = dots[i], b = dots[i + 1];
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len = Math.sqrt(dx * dx + dy * dy);
      const ang = Math.atan2(dy, dx) * 180 / Math.PI;
      lines.push({
        left: a.x, top: a.y, width: len, deg: ang,
      });
    }

    // 年报一次显示5柱，季报8柱
    const colW = period === 'annual' ? 75 : 47;
    this.setData({
      chartMetricName: name, chartBars: bars, chartField: field,
      chartColW: colW, chartMinW: bars.length * colW,
      yLabels, yLabelsR,
    });
  },

  _fmtAmount(v) {
    if (v == null) return '--';
    const n = Math.abs(v);
    if (n >= 1e8) return (v / 1e8).toFixed(1) + '亿';
    if (n >= 1e4) return (v / 1e4).toFixed(1) + '万';
    return v.toFixed(0);
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
