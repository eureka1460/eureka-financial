/**
 * history-chart — Canvas 柱状图 + 同比折线 + 双轴
 */
Component({
  properties: {
    title: { type: String, value: '' },
    data: { type: Array, value: [] },
    color: { type: String, value: '#3B82F6' },
  },

  data: {
    bars: [],
    chartWidth: 0,
  },

  observers: {
    'data'(list) {
      if (!list || list.length === 0) return;
      const n = list.length;
      const hasYoy = list.some(d => d.yoy != null);
      // 画布宽度：每柱 80px，最少 600px
      const w = Math.max(n * 80, 600);
      this.setData({ chartWidth: w, bars: list }, () => {
        setTimeout(() => this.drawChart(), 100);
      });
    },
  },

  methods: {
    drawChart() {
      const query = this.createSelectorQuery();
      query.select('#chart-canvas').fields({ node: true, size: true }).exec((res) => {
        if (!res || !res[0]) return;
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const dpr = wx.getSystemInfoSync().pixelRatio;
        const w = this.data.chartWidth;
        const h = 280;
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        ctx.scale(dpr, dpr);

        // 边距
        const L = 60, R = 50, T = 20, B = 30;
        const pw = w - L - R;
        const ph = h - T - B;
        const n = this.data.bars.length;
        const barW = Math.min(pw / n * 0.6, 36);
        const gap = pw / n;

        // 数值范围
        const vals = this.data.bars.map(d => Math.abs(d.value || 0));
        const maxV = Math.max(...vals, 1);
        // 同比范围
        const yoys = this.data.bars.map(d => d.yoy).filter(y => y != null);
        const hasYoy = yoys.length >= 2;
        let maxYoy = 0.3, minYoy = -0.3;
        if (hasYoy) {
          const absY = Math.max(...yoys.map(y => Math.abs(y)), 0.01);
          maxYoy = absY * 1.3;
          minYoy = -maxYoy;
        }

        // 背景
        ctx.fillStyle = '#fff';
        ctx.fillRect(0, 0, w, h);

        // 网格线
        ctx.strokeStyle = '#f0f0f0';
        ctx.lineWidth = 0.5;
        for (let i = 0; i <= 4; i++) {
          const y = T + ph * i / 4;
          ctx.beginPath();
          ctx.moveTo(L, y);
          ctx.lineTo(w - R, y);
          ctx.stroke();
        }

        // 左轴标签
        ctx.fillStyle = '#999';
        ctx.font = '10px sans-serif';
        ctx.textAlign = 'right';
        for (let i = 0; i <= 4; i++) {
          const v = maxV * (4 - i) / 4;
          ctx.fillText(this.fmtShort(v), L - 4, T + ph * i / 4 + 4);
        }

        // 右轴标签（YoY%）
        if (hasYoy) {
          ctx.textAlign = 'left';
          for (let i = 0; i <= 4; i++) {
            const pct = maxYoy * (4 - i) / 4;
            ctx.fillText('+' + (pct * 100).toFixed(0) + '%', w - R + 4, T + ph * i / 4 + 4);
          }
          // 0 线
          const zeroY = T + ph * (maxYoy / (maxYoy - minYoy));
          ctx.strokeStyle = '#e0e0e0';
          ctx.beginPath();
          ctx.moveTo(L, zeroY);
          ctx.lineTo(w - R, zeroY);
          ctx.stroke();
        }

        // 画柱
        const cols = this.data.bars.map((d, i) => {
          const x = L + gap * i + (gap - barW) / 2;
          const bh = (Math.abs(d.value || 0) / maxV) * ph;
          const bottom = T + ph;
          // 柱色
          ctx.fillStyle = (d.value || 0) < 0 ? '#EF4444' : this.data.color;
          ctx.fillRect(x, bottom - bh, barW, bh);
          // 数值标签
          ctx.fillStyle = '#666';
          ctx.font = '9px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(this.fmtShort(d.value || 0), x + barW / 2, bottom - bh - 4);
          // X 标签
          ctx.fillStyle = '#999';
          ctx.fillText(String(d.year || ''), x + barW / 2, bottom + 16);
          return { x: x + barW / 2, y: bottom - bh };
        });

        // 折线 + 点
        if (hasYoy) {
          const linePoints = this.data.bars.map((d, i) => {
            if (d.yoy == null) return null;
            const x = L + gap * i + gap / 2;
            const y = T + ph * (1 - (d.yoy - minYoy) / (maxYoy - minYoy));
            return { x, y, yoy: d.yoy };
          }).filter(p => p);

          // 连线
          ctx.strokeStyle = '#F59E0B';
          ctx.lineWidth = 2;
          ctx.beginPath();
          for (let i = 0; i < linePoints.length; i++) {
            if (i === 0) ctx.moveTo(linePoints[i].x, linePoints[i].y);
            else ctx.lineTo(linePoints[i].x, linePoints[i].y);
          }
          ctx.stroke();

          // 点和标签
          for (const p of linePoints) {
            ctx.fillStyle = p.yoy >= 0 ? '#22C55E' : '#EF4444';
            ctx.beginPath();
            ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = p.yoy >= 0 ? '#166534' : '#991B1B';
            ctx.font = '10px sans-serif';
            ctx.textAlign = 'center';
            const txt = (p.yoy >= 0 ? '+' : '') + (p.yoy * 100).toFixed(1) + '%';
            ctx.fillText(txt, p.x, p.y - 10);
          }
        }
      });
    },

    fmtShort(v) {
      if (v == null) return '--';
      const n = Math.abs(v);
      if (n >= 1e8) return (v / 1e8).toFixed(1) + '亿';
      if (n >= 1e4) return (v / 1e4).toFixed(1) + '万';
      if (n < 1 && n !== 0) return (v * 100).toFixed(1) + '%';
      return v.toFixed(0);
    },
  },
});
