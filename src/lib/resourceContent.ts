export interface NormalizedResourceContent {
  content: string | null
  error: 'empty' | 'mock' | 'audit' | 'invalid' | null
}

const auditKeys = new Set([
  'passed',
  'overall_score',
  'score',
  'issues',
  'suggestions',
  'corrections',
  'hallucination_detected',
  'hallucination_score',
  'debate_record',
])

function parseCompleteJson(value: string): unknown | undefined {
  let text = value.trim()
  const fenced = text.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i)
  if (fenced) text = fenced[1].trim()
  if (!text.startsWith('{') && !text.startsWith('[') && !text.startsWith('"{')) {
    return undefined
  }

  try {
    return JSON.parse(text)
  } catch {
    return undefined
  }
}

/**
 * Last-line protection for generated resources.  The API normally returns
 * Markdown, but historical records can contain escaped JSON or audit payloads.
 */
export function normalizeResourceContent(raw: unknown): NormalizedResourceContent {
  let value = raw

  for (let depth = 0; depth < 3; depth += 1) {
    if (typeof value === 'string') {
      const parsed = parseCompleteJson(value)
      if (parsed === undefined) {
        const content = value.trim()
        return content ? { content, error: null } : { content: null, error: 'empty' }
      }
      value = parsed
      continue
    }

    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      return { content: null, error: 'invalid' }
    }

    const payload = value as Record<string, unknown>
    const meta = payload._meta
    if (
      meta &&
      typeof meta === 'object' &&
      (meta as Record<string, unknown>).model === 'mock'
    ) {
      return { content: null, error: 'mock' }
    }

    if (Object.keys(payload).some((key) => auditKeys.has(key))) {
      return { content: null, error: 'audit' }
    }

    value = payload.content
  }

  return { content: null, error: 'invalid' }
}
