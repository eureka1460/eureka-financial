/**
 * filter-condition 组件
 * 筛选条件卡片
 *
 * Props:
 *   condition: { metric, expression, operator, value, consecutive_years }
 *   index: 序号
 *   metricLabel: 指标中文名
 */
Component({
  properties: {
    condition: { type: Object, value: {} },
    index: { type: Number, value: 0 },
    metricLabel: { type: String, value: '' },
  },

  data: {
    display: '',
    opText: '',
  },

  observers: {
    'condition, metricLabel'(cond, label) {
      if (!cond) return;

      const opMap = {
        '>=': '≥',
        '>': '>',
        '<=': '≤',
        '<': '<',
        '==': '=',
        '!=': '≠',
      };
      const opText = opMap[cond.operator] || cond.operator;
      const name = label || cond.metric || cond.expression || '?';
      const years =
        cond.consecutive_years && cond.consecutive_years > 1
          ? ` 连续${cond.consecutive_years}年`
          : '';

      this.setData({
        display: `${name} ${opText} ${cond.value}${years}`,
        opText,
      });
    },
  },

  methods: {
    onRemove() {
      this.triggerEvent('remove', { index: this.data.index });
    },
  },
});
