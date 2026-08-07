import { describe, expect, it } from 'vitest'
import { normalizeResourceContent } from './resourceContent'

describe('normalizeResourceContent', () => {
  it('keeps Markdown content unchanged', () => {
    expect(normalizeResourceContent('# Valid resource\n\nContent.')).toEqual({
      content: '# Valid resource\n\nContent.',
      error: null,
    })
  })

  it('unwraps a valid DeepSeek resource envelope', () => {
    expect(
      normalizeResourceContent(JSON.stringify({ content: '# Generated\n\nBody' })),
    ).toEqual({ content: '# Generated\n\nBody', error: null })
  })

  it('unwraps fenced JSON without exposing the envelope', () => {
    expect(
      normalizeResourceContent('```json\n{"content":"# Fenced guide"}\n```'),
    ).toEqual({ content: '# Fenced guide', error: null })
  })

  it('does not render mock or audit payloads as resources', () => {
    expect(
      normalizeResourceContent(JSON.stringify({ content: '# Mock', _meta: { model: 'mock' } })),
    ).toEqual({ content: null, error: 'mock' })
    expect(
      normalizeResourceContent(JSON.stringify({ passed: true, score: 88, issues: [] })),
    ).toEqual({ content: null, error: 'audit' })
  })
})
