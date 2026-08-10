import type { TutoringQuestion } from '@/api/core'
import type { PersistedSession } from './types'

export const SESSION_STORAGE_PREFIX = 'adaptive-guidance-session'
export const EXIT_STORAGE_PREFIX = 'adaptive-guidance-exited'

export function sessionStorageKey(learnerId: number): string {
  return `${SESSION_STORAGE_PREFIX}:${learnerId}`
}

export function exitStorageKey(learnerId: number): string {
  return `${EXIT_STORAGE_PREFIX}:${learnerId}`
}

export function createSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

export function readPersistedSession(learnerId: number): PersistedSession | null {
  try {
    const raw = window.localStorage.getItem(sessionStorageKey(learnerId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as PersistedSession
    if (!parsed?.config?.topic || !Array.isArray(parsed.questions) || parsed.questions.length === 0) return null
    return parsed
  } catch {
    return null
  }
}

export function mergeQuestions(persisted: PersistedSession, remote: TutoringQuestion[]): TutoringQuestion[] {
  const merged = [...persisted.questions]
  const knownIds = new Set(merged.map((question) => question.id))
  remote.forEach((question) => {
    if (!knownIds.has(question.id)) merged.push(question)
  })
  return merged
}

export function formatHistoryDate(value: string): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function formatUserAnswer(answer: unknown): string {
  if (Array.isArray(answer)) return answer.map(String).join(', ')
  if (answer === null || answer === undefined || answer === '') return '未记录'
  return String(answer)
}
