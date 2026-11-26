// 统一的数字与文案格式化工具
export const pct = (v, digits = 1) => `${((v ?? 0) * 100).toFixed(digits)}%`
export const num = (v, digits = 0) =>
  Number(v ?? 0).toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
export const money = (v, digits = 0) => `¥${num(v, digits)}`
export const fixed = (v, digits = 2) => Number(v ?? 0).toFixed(digits)

export const PALETTE = [
  '#3b6cf6',
  '#12b8a6',
  '#f5a524',
  '#8b5cf6',
  '#ef5b7b',
  '#2aa9e0',
  '#7cb342',
  '#f97316',
]

export const axisStyle = {
  axisLine: { lineStyle: { color: '#dfe3ee' } },
  axisTick: { show: false },
  axisLabel: { color: '#6b7280', fontSize: 12 },
  splitLine: { lineStyle: { color: '#eef1f7' } },
}
