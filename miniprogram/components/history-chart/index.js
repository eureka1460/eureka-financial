/**
 * history-chart 组件 — 历年财务数据柱状图
 *
 * Props:
 *   data: [{ year, value, yoy, label }] 按年份排序
 *   title: 图表标题
 *   unit: 单位（元 / %）
 *   color: 柱状颜色
 */
Component({
  properties: {
    title: { type: String, value: '' },
    data: { type: Array, value: [] },
    unit: { type: String, value: '元' },
    color: { type: String, value: '#3B82F6' },
  },

  data: {
    bars: [],
    maxVal: 1,
  },

  observers: {
    data(list) {
      if (!list || list.length === 0) return;
      const vals = list.map((d) => Math.abs(d.value || 0));
      const max = Math.max(...vals, 1);
      const bars = list.map((d) => ({
        ...d,
        height: Math.round(((d.value || 0) / max) * 100),
        displayVal: this.fmtVal(d.value),
        yoyText: d.yoy != null ? (d.yoy >= 0 ? '+' + (d.yoy * 100).toFixed(1) + '%' : (d.yoy * 100).toFixed(1) + '%') : '',
        yoyDown: d.yoy != null && d.yoy < 0,
      }));
      this.setData({ bars, maxVal: max });
    },
  },

  methods: {
    fmtVal(v) {
      if (v == null) return '--';
      const n = Math.abs(v);
      if (n >= 1e8) return (v / 1e8).toFixed(2) + '亿';
      if (n >= 1e4) return (v / 1e4).toFixed(1) + '万';
      if (n < 1 && n !== 0) return (v * 100).toFixed(1) + '%';
      return v.toFixed(2);
    },
  },
});
