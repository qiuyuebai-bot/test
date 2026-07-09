/**
 * Sentry 错误聚合集成
 *
 * 设计目标：
 *  - DSN 未配置时全量降级为 no-op，零侵入、零运行时开销
 *  - DSN 配置后自动采集未捕获异常、Promise 拒绝与 API 错误
 *  - 与 ErrorBoundary 协同，避免重复上报
 *  - 业务错误（ApiError 4xx）默认不上报，仅上报 5xx 与未预期错误
 *
 * 启用方式：在 .env 中设置 VITE_SENTRY_DSN + VITE_SENTRY_ENVIRONMENT
 */

import type * as SentryTypes from '@sentry/react'

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined
const SENTRY_ENV = (import.meta.env.VITE_SENTRY_ENVIRONMENT as string) || 'development'
const SENTRY_SAMPLE_RATE = Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? '0.1')

let initialized = false
let sentryClient: {
  captureException: (err: unknown, context?: Record<string, unknown>) => string | undefined
  setUser: (user: { id: string; username: string; role?: string } | null) => void
  captureMessage: (msg: string, level?: string) => void
} | null = null

async function loadSentry(): Promise<typeof sentryClient> {
  if (sentryClient || !SENTRY_DSN) return sentryClient
  try {
    const Sentry = await import('@sentry/react')
    Sentry.init({
      dsn: SENTRY_DSN,
      environment: SENTRY_ENV,
      release: import.meta.env.VITE_APP_VERSION ?? '1.0.0',
      tracesSampleRate: SENTRY_SAMPLE_RATE,
      sampleRate: 1.0,
      maxBreadcrumbs: 30,
      attachStacktrace: true,
      sendDefaultPii: false,
      beforeBreadcrumb(breadcrumb) {
        if (breadcrumb.category === 'fetch' && breadcrumb.data) {
          const url = String(breadcrumb.data['url'] ?? '')
          if (url.includes('/auth/')) return null
        }
        return breadcrumb
      },
      beforeSend(event) {
        if (!event.exception?.values?.length) return event
        const first = event.exception.values[0]
        const status = Number(first.mechanism?.data?.status ?? 0)
        if (status >= 400 && status < 500) return null
        return event
      },
    })
    sentryClient = {
      captureException: (err, ctx) => Sentry.captureException(err, ctx),
      setUser: (user) => Sentry.setUser(user),
      captureMessage: (msg, level) => Sentry.captureMessage(msg, { level: level as SentryTypes.SeverityLevel }),
    }
    initialized = true
    return sentryClient
  } catch (e) {
    console.warn('[Sentry] 初始化失败，降级为 no-op', e)
    return null
  }
}

export function initSentry(): void {
  if (!SENTRY_DSN) {
    return
  }
  void loadSentry()
}

export function isSentryEnabled(): boolean {
  return initialized
}

export interface ReportContext {
  tags?: Record<string, string | number | boolean>
  extra?: Record<string, unknown>
  user?: { id: string; username: string; role?: string }
}

export function reportError(error: unknown, context?: ReportContext): void {
  if (!initialized || !sentryClient) {
    if (import.meta.env.DEV) {
      console.error('[reportError] Sentry 未启用，错误仅控制台输出:', error, context)
    }
    return
  }
  try {
    if (context?.user) {
      sentryClient.setUser(context.user)
    }
    sentryClient.captureException(error, {
      tags: context?.tags,
      extra: context?.extra,
    })
  } catch (e) {
    console.warn('[Sentry] 上报失败:', e)
  }
}

export function reportMessage(message: string, level: 'info' | 'warning' | 'error' = 'info'): void {
  if (!initialized || !sentryClient) return
  try {
    sentryClient.captureMessage(message, level)
  } catch (e) {
    console.warn('[Sentry] 消息上报失败:', e)
  }
}

export function setSentryUser(user: { id: string; username: string; role?: string } | null): void {
  if (!initialized || !sentryClient) return
  sentryClient.setUser(user)
}

export { SENTRY_DSN, SENTRY_ENV }
