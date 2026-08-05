export type Credibility = 'high' | 'medium' | 'low' | 'noEvidence'

export type HallucinationClaimStatus = 'supported' | 'weakSupport' | 'contradicted' | 'insufficientEvidence'

export interface HallucinationClaim {
  text: string
  status: HallucinationClaimStatus
  similarity: number | null
  entities: string[]
  citations: string[]
  reason: string
}

export interface HallucinationCitation {
  label: string
  title: string
  paragraph: number
  docId?: number
  sliceId?: number
}

export interface HallucinationReport {
  detected: boolean
  score: number
  confidence: number
  credibility: Credibility
  evidenceCoverage: number
  claims: HallucinationClaim[]
  citations: HallucinationCitation[]
  knowledgeGap: {
    present: boolean
    claims: string[]
    entities: string[]
    attributes: string[]
    uploadPrompt: string
  }
}

const defaultReport = (): HallucinationReport => ({
  detected: false,
  score: 0,
  confidence: 0,
  credibility: 'noEvidence',
  evidenceCoverage: 0,
  claims: [],
  citations: [],
  knowledgeGap: {
    present: false,
    claims: [],
    entities: [],
    attributes: [],
    uploadPrompt: 'Upload relevant materials to improve evidence coverage.',
  },
})

const credibilityValue = (value: unknown): Credibility => {
  if (value === 'high' || value === 'medium' || value === 'low') return value
  return 'noEvidence'
}

const claimStatus = (value: unknown): HallucinationClaimStatus => {
  if (value === 'supported' || value === 'contradicted') return value
  if (value === 'weak_support' || value === 'weakSupport') return 'weakSupport'
  return 'insufficientEvidence'
}

export function normalizeHallucinationReport(raw: unknown): HallucinationReport {
  if (!raw || typeof raw !== 'object') return defaultReport()
  const value = raw as Record<string, unknown>
  const gap = (value.knowledgeGap ?? value.knowledge_gap) as Record<string, unknown> | undefined
  const claims = Array.isArray(value.claims) ? value.claims : []
  const citations = Array.isArray(value.citations) ? value.citations : []
  const normalized = defaultReport()

  normalized.detected = value.detected === true || value.hallucinationDetected === true || value.hallucination_detected === true
  normalized.score = typeof value.score === 'number' ? value.score : typeof value.hallucinationScore === 'number' ? value.hallucinationScore : 0
  normalized.confidence = typeof value.confidence === 'number' ? value.confidence : 0
  normalized.credibility = credibilityValue(value.credibility)
  const coverage = value.evidenceCoverage ?? value.evidence_coverage
  normalized.evidenceCoverage = typeof coverage === 'number' ? coverage : 0
  normalized.claims = claims.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object').map(item => ({
    text: typeof item.text === 'string' ? item.text : '',
    status: claimStatus(item.status),
    similarity: typeof item.similarity === 'number' ? item.similarity : null,
    entities: Array.isArray(item.entities) ? item.entities.filter((entity): entity is string => typeof entity === 'string') : [],
    citations: Array.isArray(item.citations) ? item.citations.filter((citation): citation is string => typeof citation === 'string') : [],
    reason: typeof item.reason === 'string' ? item.reason : '',
  }))
  normalized.citations = citations.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object').flatMap(item => {
    if (typeof item.label !== 'string' || typeof item.title !== 'string' || typeof item.paragraph !== 'number') return []
    return [{ label: item.label, title: item.title, paragraph: item.paragraph, docId: typeof item.docId === 'number' ? item.docId : typeof item.doc_id === 'number' ? item.doc_id : undefined, sliceId: typeof item.sliceId === 'number' ? item.sliceId : typeof item.slice_id === 'number' ? item.slice_id : undefined }]
  })
  normalized.knowledgeGap = {
    present: gap?.present === true,
    claims: Array.isArray(gap?.claims) ? gap.claims.filter((claim): claim is string => typeof claim === 'string') : [],
    entities: Array.isArray(gap?.entities) ? gap.entities.filter((entity): entity is string => typeof entity === 'string') : [],
    attributes: Array.isArray(gap?.attributes) ? gap.attributes.filter((attribute): attribute is string => typeof attribute === 'string') : [],
    uploadPrompt: typeof gap?.uploadPrompt === 'string' ? gap.uploadPrompt : typeof gap?.upload_prompt === 'string' ? gap.upload_prompt : normalized.knowledgeGap.uploadPrompt,
  }
  if (normalized.knowledgeGap.present && normalized.credibility === 'high') normalized.credibility = 'noEvidence'
  return normalized
}

