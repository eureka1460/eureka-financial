/**
 * history-chart — 纯CSS柱状图 + 同比标签
 */
Component({
  properties: {
    title: { type: String, value: '' },
    data: { type: Array, value: [] },
    color: { type: String, value: '#3B82F6' },
  },

  data: { list: [], hasLine: false },

  observers: {
    'data'(raw) {
      if (!raw || raw.length === 0) return;
      const vals = raw.map(d => Math.abs(d.value || 0));
      const max = Math.max(...vals, 1);
      const hasYoy = raw.some(d => d.yoy != null);
      const list = raw.map(d => {
        const v = d.value || 0;
        return {
          ...d,
          _h: Math.round((Math.abs(v) / max) * 100),
          _neg: v < 0,
          _val: this.fmtV(v),
          _lbl: d.year,
          _color: this.data.color,
          _yoyTxt: d.yoy != null ? (d.yoy >= 0 ? '+' : '') + (d.yoy * 100).toFixed(1) + '%' : '',
          _yoyCls: d.yoy != null ? (d.yoy >= 0 ? 'text-up' : 'text-down') : '',
        };
      });
      this.setData({ list, hasLine: hasYoy });
    },
  },

  methods: {
    fmtV(v) {
      if (v == null) return '--';
      const n = Math.abs(v);
      if (n >= 1e8) return (v / 1e8).toFixed(1) + '亿';
      if (n >= 1e4) return (v / 1e4).toFixed(1) + '万';
      return v.toFixed(0);
    },
  },
});
