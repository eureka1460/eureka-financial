/**
 * 数字格式化工具
 */

/** 百分比（小数 → 百分比字符串）  0.325 → "32.50%" */
function fmtPercent(val, decimals = 2) {
  if (val === null || val === undefined) return '--';
  const n = Number(val);
  if (isNaN(n)) return '--';
  return (n * 100).toFixed(decimals) + '%';
}

/** 大额金额（元 → 亿/万/元） */
function fmtAmount(val) {
  if (val === null || val === undefined) return '--';
  const n = Number(val);
  if (isNaN(n)) return '--';
  const abs = Math.abs(n);
  if (abs >= 1e8) return (n / 1e8).toFixed(2) + '亿';
  if (abs >= 1e4) return (n / 1e4).toFixed(2) + '万';
  return n.toFixed(2) + '元';
}

/** 比率（已为百分比显示的数值） 0.325 → "0.33" */
function fmtRatio(val, decimals = 2) {
  if (val === null || val === undefined) return '--';
  const n = Number(val);
  if (isNaN(n)) return '--';
  return n.toFixed(decimals);
}

/** 小数 → 0~1 之间的值，用于进度条宽度 */
function toBarValue(val) {
  if (val === null || val === undefined) return 0;
  const n = Number(val);
  if (isNaN(n)) return 0;
  return Math.min(Math.max(n, 0), 1);
}

/** 带正负号 */
function fmtSigned(val, decimals = 2) {
  if (val === null || val === undefined) return '--';
  const n = Number(val);
  if (isNaN(n)) return '--';
  const sign = n >= 0 ? '+' : '';
  return sign + n.toFixed(decimals);
}

/** 日期 YYYY-MM-DD → YYYY年MM月DD日 */
function fmtDate(d) {
  if (!d) return '--';
  const parts = String(d).split('-');
  if (parts.length === 3) {
    return parts[0] + '年' + parseInt(parts[1]) + '月' + parseInt(parts[2]) + '日';
  }
  return d;
}

/** 报表类型 → 中文 */
function fmtReportType(type) {
  const map = {
    annual: '年报',
    semi_annual: '中报',
    q1: '一季报',
    q3: '三季报',
  };
  return map[type] || type || '--';
}

module.exports = {
  fmtPercent,
  fmtAmount,
  fmtRatio,
  toBarValue,
  fmtSigned,
  fmtDate,
  fmtReportType,
};
