Component({
  properties: {
    title: { type: String, value: '' },
    chartData: { type: Array, value: [] },
    color: { type: String, value: '#3B82F6' },
  },

  data: { list: [], hasLine: false },

  observers: {
    'chartData': function(raw) {
      this.onData(raw);
    },
  },

  methods: {
    onData(raw) {
      if (!raw || raw.length < 1) return;
      const vals = raw.map(d => Math.abs(d.value || 0));
      const max = Math.max(...vals, 1);
      const hasLine = raw.filter(d => d.yoy != null).length >= 2;

      // 同比范围（用于折线Y坐标映射）
      const yoyVals = raw.map(d => d.yoy).filter(y => y != null);
      const yoyAbsMax = yoyVals.length ? Math.max(...yoyVals.map(Math.abs), 0.01) * 1.3 : 0.3;

      const list = raw.map((d, i) => {
        const v = d.value || 0;
        const y = d.yoy;
        return {
          year: d.year,
          _h: Math.round((Math.abs(v) / max) * 100),
          _neg: v < 0,
          _val: this.fmt(v),
          _yoy: y != null ? (y >= 0 ? '+' : '') + (y * 100).toFixed(1) + '%' : '',
          _yoyUp: y != null && y >= 0,
          _yoyDn: y != null && y < 0,
          _yoyNone: y == null,
          // 折线Y坐标：50=中位线, 上负下正
          _dotY: y != null ? 50 - (y / yoyAbsMax) * 45 : 50,
          // 连线角度
          _nextY: null, _lineDeg: null, _lineLen: null,
        };
      });

      // 计算连线
      for (let i = 0; i < list.length - 1; i++) {
        if (raw[i].yoy != null && raw[i+1].yoy != null) {
          const dy = list[i+1]._dotY - list[i]._dotY;
          const dx = 100;
          list[i]._nextY = list[i+1]._dotY;
          list[i]._lineDeg = Math.atan2(dy, dx) * 180 / Math.PI;
          list[i]._lineLen = Math.sqrt(dx * dx + dy * dy);
        }
      }

      this.setData({ list, hasLine });
    },

    fmt(v) {
      if (v == null) return '--';
      const n = Math.abs(v);
      if (n >= 1e8) return (v / 1e8).toFixed(1) + '亿';
      if (n >= 1e4) return (v / 1e4).toFixed(1) + '万';
      return v.toFixed(0);
    },
  },
});
