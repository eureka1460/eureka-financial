/**
 * metric-bar 组件
 * 指标进度条
 *
 * Props:
 *   label: 指标名称
 *   value: 当前值（小数形式，如 0.32 表示 32%）
 *   showValue: 显示的数值文本
 *   max: 进度条最大参考值（默认 0.5 即 50%）
 *   color: 进度条颜色（默认蓝色）
 */
Component({
  properties: {
    label: String,
    value: { type: Number, value: 0 },
    showValue: String,
    max: { type: Number, value: 0.5 },
    color: { type: String, value: 'var(--color-accent)' },
    field: { type: String, value: '' },
  },

  methods: {
    onTap() {
      if (this.data.field) {
        this.triggerEvent('tapmetric', {
          field: this.data.field,
          name: this.data.label,
        });
      }
    },
  },

  data: {
    barPercent: 0,
  },

  observers: {
    'value, max'(val, max) {
      const ratio = Math.min((val || 0) / (max || 0.5), 1);
      this.setData({ barPercent: Math.round(ratio * 100) });
    },
  },
});
