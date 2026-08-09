import { describe, expect, it } from 'vitest'
import { normalizeHallucinationReport } from './hallucinationEvidence'

describe('hallucination evidence adapter', () => {
  it('keeps sufficient evidence and citations', () => {
    const report = normalizeHallucinationReport({
      credibility: 'high',
      evidence_coverage: 1,
      citations: [{ label: '[Python Release Notes-Paragraph 3]', title: 'Python Release Notes', paragraph: 3 }],
      claims: [{ text: 'Python 3.12 adds improved errors.', status: 'supported', similarity: 0.86, citations: ['[Python Release Notes-Paragraph 3]'] }],
    })

    expect(report.credibility).toBe('high')
    expect(report.citations[0].label).toBe('[Python Release Notes-Paragraph 3]')
  })

  it('defaults an evidence gap to noEvidence with upload guidance', () => {
    const report = normalizeHallucinationReport({
      knowledge_gap: { present: true, entities: ['Aurora'] },
    })

    expect(report.credibility).toBe('noEvidence')
    expect(report.knowledgeGap.entities).toContain('Aurora')
    expect(report.knowledgeGap.uploadPrompt).toBeTruthy()
  })

  it('translates the legacy English upload prompt', () => {
    const report = normalizeHallucinationReport({
      credibility: 'no_evidence',
      knowledge_gap: {
        present: true,
        upload_prompt: 'Upload relevant materials to improve evidence coverage.',
      },
    })

    expect(report.knowledgeGap.uploadPrompt).toBe('上传相关资料以提升证据覆盖率。')
  })
})
