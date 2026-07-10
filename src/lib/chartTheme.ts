/**
 * 共享图表主题
 * 统一 Recharts 图表配色与样式，绑定 CSS 变量以跟随明暗主题切换
 */

export const CHART_COLORS = {
  primary: 'var(--color-viz-1)',
  secondary: 'var(--color-viz-2)',
  tertiary: 'var(--color-viz-3)',
  quaternary: 'var(--color-viz-4)',
  grid: 'var(--color-border)',
  text: 'var(--color-text-secondary)',
} as const

export const CHART_TOOLTIP_PROPS = {
  contentStyle: {
    background: 'var(--color-bg-card)',
    border: '1px solid var(--color-border)',
    borderRadius: '8px',
    fontSize: '12px',
    color: 'var(--color-text-primary)',
    boxShadow: '0 4px 16px var(--shadow-medium)',
  },
  labelStyle: { color: 'var(--color-text-secondary)', fontWeight: 500 },
  itemStyle: { color: 'var(--color-text-primary)' },
} as const

export const CHART_GRID_PROPS = {
  strokeDasharray: '3 3',
  stroke: 'var(--color-border)',
  vertical: false,
} as const

export const CHART_AXIS_PROPS = {
  tick: { fill: 'var(--color-text-tertiary)', fontSize: 12 },
  axisLine: { stroke: 'var(--color-border)' },
  tickLine: false,
} as const
