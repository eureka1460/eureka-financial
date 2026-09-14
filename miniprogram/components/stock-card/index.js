/**
 * stock-card 组件
 * 股票列表项卡片
 *
 * Props:
 *   stock: { symbol, name, industry, market, ... }
 *   metric: { roe, gross_margin, net_profit_yoy, ... } (optional)
 */
const { fmtPercent } = require('../../utils/format');

Component({
  properties: {
    stock: {
      type: Object,
      value: {},
    },
    metric: {
      type: Object,
      value: null,
    },
    showIndustry: {
      type: Boolean,
      value: true,
    },
  },

  data: {
    roe: '--',
    grossMargin: '--',
    profitYoY: '--',
    profitYoYClass: '',
    marketLabel: '',
  },

  observers: {
    'stock, metric'(stock, metric) {
      if (!stock) return;

      const data = {};

      // 交易所标签
      const marketMap = { SH: '沪', SZ: '深', BJ: '北' };
      data.marketLabel = marketMap[stock.market] || stock.market || '';

      // 指标
      if (metric) {
        data.roe = fmtPercent(metric.roe);
        data.grossMargin = fmtPercent(metric.gross_margin);
        const yoy = fmtPercent(metric.net_profit_yoy);
        data.profitYoY = yoy;
        // 预计算涨跌样式（WXML 不支持 .indexOf）
        data.profitYoYClass = yoy.startsWith('-') && yoy !== '--' ? 'text-down' : 'text-up';
      }

      this.setData(data);
    },
  },

  methods: {
    onTap() {
      const symbol = String((this.data.stock && this.data.stock.symbol) || '').trim();
      if (!symbol) return;
      this.triggerEvent('stocktap', { symbol });
    },
  },
});
