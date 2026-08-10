import type { MetricResult } from '@/types'

export const METRIC_STATUS_LABELS: Record<MetricResult['status'], string> = {
  ready: '已就绪',
  collecting: '样本不足',
  no_data: '暂无数据',
  not_applicable: '不适用',
  stale: '数据过期',
  error: '计算失败',
}

export function findMetric(results: MetricResult[] | undefined, metricId: string): MetricResult | null {
  return results?.find((metric) => metric.metricId === metricId) ?? null
}

export function formatMetricValue(
  metric: MetricResult | null | undefined,
  pending = '暂无数据',
  decimals = 1,
): string {
  if (!metric || typeof metric.value !== 'number') return pending
  return metric.unit === '%' ? `${metric.value.toFixed(decimals)}%` : metric.value.toFixed(decimals)
}

export function metricStatusLabel(metric: MetricResult | null | undefined, fallback = '暂无数据'): string {
  if (!metric) return fallback
  return METRIC_STATUS_LABELS[metric.status] ?? fallback
}

export function metricReady(metric: MetricResult | null | undefined): boolean {
  return metric?.status === 'ready' && typeof metric.value === 'number'
}

export function metricProgressValue(metric: MetricResult | null | undefined): number {
  return typeof metric?.value === 'number' ? metric.value : 0
}
