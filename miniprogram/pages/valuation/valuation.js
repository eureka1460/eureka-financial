/**
 * 估值计算页：DCF + DDM
 */
const api = require('../../utils/api');

function fmoney(val) {
  if (val === null || val === undefined) return '--';
  return Number(val).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmoneyUnit(val) {
  if (val === null || val === undefined) return '--';
  const n = Number(val);
  const abs = Math.abs(n);
  if (abs >= 1e8) return (n / 1e8).toFixed(2) + ' 亿';
  if (abs >= 1e4) return (n / 1e4).toFixed(2) + ' 万';
  return n.toFixed(2);
}

Page({
  data: {
    symbol: '',

    activeTab: 'dcf',

    dcfParams: {
      symbol: '',
      fcf_base: '',
      forecast_years: 5,
      growth_rate_stage1: 0.10,
      growth_rate_terminal: 0.03,
      wacc: 0.08,
      net_debt: '',
      total_shares: '',
    },

    ddmParams: {
      symbol: '',
      d0: '',
      forecast_years: 5,
      growth_rate_stage1: 0.08,
      growth_rate_terminal: 0.02,
      required_return: 0.07,
    },

    // WACC 明细
    showWaccDetail: false,
    waccDetail: {},

    // 格式化后的 DCF 结果
    dcfFairValue: '--',
    dcfEnterpriseValue: '--',
    dcfEquityValue: '--',
    dcfPvStage1: '--',
    dcfPvTerminal: '--',
    dcfInputParams: '',

    // 格式化后的 DDM 结果
    ddmFairValue: '--',
    ddmPvStage1: '--',
    ddmPvTerminal: '--',
    ddmInputParams: '',

    // 原始结果（用于判断是否已计算）
    dcfDone: false,
    ddmDone: false,

    loading: false,
    error: '',
  },

  onLoad(options) {
    const symbol = options.symbol || '';
    if (symbol) {
      this.setData({
        symbol,
        'dcfParams.symbol': symbol,
        'ddmParams.symbol': symbol,
      });
      wx.setNavigationBarTitle({ title: `估值 - ${symbol}` });
    }
  },

  onTabTap(e) {
    this.setData({ activeTab: e.currentTarget.dataset.tab });
  },

  onDcfInput(e) {
    const field = e.currentTarget.dataset.field;
    let val = e.detail.value;
    if (val !== '' && field !== 'symbol') val = parseFloat(val);
    const update = { [`dcfParams.${field}`]: val };
    // 股票代码同步到两个 tab
    if (field === 'symbol') {
      update['ddmParams.symbol'] = val;
      update.symbol = val;
    }
    this.setData(update);
  },

  onDdmInput(e) {
    const field = e.currentTarget.dataset.field;
    let val = e.detail.value;
    if (val !== '' && field !== 'symbol') val = parseFloat(val);
    const update = { [`ddmParams.${field}`]: val };
    // 股票代码同步到两个 tab
    if (field === 'symbol') {
      update['dcfParams.symbol'] = val;
      update.symbol = val;
    }
    this.setData(update);
  },

  betaIndustries: [
    '食品饮料(0.8)', '医药生物(0.9)', '银行(0.9)', '非银金融(1.0)',
    '电子(1.3)', '计算机(1.3)', '电力设备(1.2)', '汽车(1.1)',
    '军工(1.1)', '公用事业(0.7)', '交通运输(0.9)', '房地产(1.0)',
    '化工(1.2)', '有色金属(1.2)', '家用电器(0.9)',
  ],
  betaValues: [0.8, 0.9, 0.9, 1.0, 1.3, 1.3, 1.2, 1.1, 1.1, 0.7, 0.9, 1.0, 1.2, 1.2, 0.9],
  selectedIndustry: '',

  onPickBeta(e) {
    const idx = e.detail.value;
    const beta = this.data.betaValues[idx];
    const industry = this.data.betaIndustries[idx];
    const detail = { ...this.data.waccDetail, beta };
    // 重算 WACC
    const ew = detail.equity_weight || 0;
    const dw = 1 - ew;
    const coe = (detail.risk_free_rate || 0) + beta * (detail.market_premium || 0.055);
    const cod = detail.cost_of_debt || 0;
    const tax = detail.tax_rate || 0.25;
    detail.wacc = +(ew * coe + dw * cod * (1 - tax)).toFixed(4);
    this.setData({ waccDetail: detail, 'dcfParams.wacc': detail.wacc, selectedIndustry: industry });
  },

  onToggleWacc() {
    this.setData({ showWaccDetail: !this.data.showWaccDetail });
  },

  onWaccInput(e) {
    const field = e.currentTarget.dataset.field;
    const val = parseFloat(e.detail.value) || 0;
    const detail = { ...this.data.waccDetail, [field]: val };
    // 重新计算 WACC = 权益占比 × (Rf + β × 溢价) + 负债权重 × 债务成本 × (1 - 税率)
    const ew = detail.equity_weight || 0;
    const dw = 1 - ew;
    const coe = (detail.risk_free_rate || 0) + (detail.beta || 1) * (detail.market_premium || 0.055);
    const cod = detail.cost_of_debt || 0;
    const tax = detail.tax_rate || 0.25;
    detail.wacc = +(ew * coe + dw * cod * (1 - tax)).toFixed(4);
    this.setData({ waccDetail: detail, 'dcfParams.wacc': detail.wacc });
  },

  onCalcDCF() {
    const p = this.data.dcfParams;
    if (!p.symbol) {
      wx.showToast({ title: '请输入股票代码', icon: 'none' });
      return;
    }

    this.setData({ loading: true, error: '', dcfDone: false });

    const body = {
      symbol: p.symbol,
      forecast_years: p.forecast_years,
      growth_rate_stage1: p.growth_rate_stage1,
      growth_rate_terminal: p.growth_rate_terminal,
      wacc: p.wacc,
    };
    if (p.fcf_base !== '') body.fcf_base = p.fcf_base;
    if (p.net_debt !== '') body.net_debt = p.net_debt;
    if (p.total_shares !== '') body.total_shares = p.total_shares;

    api.calcDCF(body)
      .then((res) => {
        const r = res.data.result;
        this.setData({
          dcfFairValue: '¥' + r.fair_value_per_share.toFixed(2),
          dcfEnterpriseValue: fmoneyUnit(r.enterprise_value),
          dcfEquityValue: fmoneyUnit(r.equity_value),
          dcfPvStage1: fmoneyUnit(r.pv_stage1),
          dcfPvTerminal: fmoneyUnit(r.pv_terminal),
          dcfInputParams: JSON.stringify(res.data.input_params, null, 2),
          dcfDone: true,
          loading: false,
          waccDetail: res.data.wacc_detail || {},
        });
      })
      .catch((err) => {
        this.setData({
          loading: false,
          error: err.message || '估值计算失败',
        });
      });
  },

  onCalcDDM() {
    const p = this.data.ddmParams;
    if (!p.symbol) {
      wx.showToast({ title: '请输入股票代码', icon: 'none' });
      return;
    }

    this.setData({ loading: true, error: '', ddmDone: false });

    const body = {
      symbol: p.symbol,
      forecast_years: p.forecast_years,
      growth_rate_stage1: p.growth_rate_stage1,
      growth_rate_terminal: p.growth_rate_terminal,
      required_return: p.required_return,
    };
    if (p.d0 !== '') body.d0 = p.d0;

    api.calcDDM(body)
      .then((res) => {
        const r = res.data.result;
        this.setData({
          ddmFairValue: '¥' + r.fair_value_per_share.toFixed(2),
          ddmPvStage1: fmoneyUnit(r.pv_stage1),
          ddmPvTerminal: fmoneyUnit(r.pv_terminal),
          ddmInputParams: JSON.stringify(res.data.input_params, null, 2),
          ddmDone: true,
          loading: false,
        });
      })
      .catch((err) => {
        this.setData({
          loading: false,
          error: err.message || '估值计算失败',
        });
      });
  },
});
