/**
 * history-chart 组件 — 柱状图 + 同比折线叠加
 */
Component({
  properties: {
    title: { type: String, value: '' },
    data: { type: Array, value: [] },
    unit: { type: String, value: '元' },
    color: { type: String, value: '#3B82F6' },
  },

  data: {
    bars: [], maxVal: 1, hasNegative: false,
    linePoints: [], lineMax: 1, lineMin: 0, showLine: false,
  },

  observers: {
    data(list) {
      if (!list || list.length === 0) return;
      const absVals = list.map((d) => Math.abs(d.value || 0));
      const max = Math.max(...absVals, 1);
      const hasNeg = list.some((d) => (d.value || 0) < 0);

      const bars = list.map((d) => {
        const v = d.value || 0;
        return {
          ...d,
          height: Math.round((Math.abs(v) / max) * 100),
          isNeg: v < 0,
          displayVal: this.fmtVal(v),
          yoyText: d.yoy != null ? (d.yoy >= 0 ? '+' + (d.yoy * 100).toFixed(1) + '%' : (d.yoy * 100).toFixed(1) + '%') : '',
          yoyDown: d.yoy != null && d.yoy < 0,
        };
      });

      // 折线：同比数据
      const yoys = list.map((d) => d.yoy).filter((y) => y != null);
      const showLine = yoys.length >= 2;
      let lineMax = 1, lineMin = 0, linePoints = [];
      if (showLine) {
        const absYoys = yoys.map((y) => Math.abs(y));
        const m = Math.max(...absYoys, 0.01);
        lineMax = m * 1.3;
        lineMin = -lineMax;
        linePoints = list.map((d) => {
          if (d.yoy == null) return { x: 0, y: 50, label: '' };
          return {
            y: 50 - (d.yoy / lineMax) * 45,
            label: (d.yoy >= 0 ? '+' : '') + (d.yoy * 100).toFixed(1) + '%',
            isDown: d.yoy < 0,
          };
        });
      }

      this.setData({ bars, maxVal: max, hasNegative: hasNeg, linePoints, lineMax, lineMin, showLine });
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
