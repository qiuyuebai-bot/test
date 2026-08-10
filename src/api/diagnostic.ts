import { http } from '../lib/request'

export interface DiagnosticQuestion {
  id: string
  type: 'single' | 'multiple' | string
  topic: string
  question: string
  options: string[]
  difficulty: number
  knowledgePoints: string[]
  generationMethod?: string
  assessmentMode: 'diagnostic' | 'practice' | string
  abilityDimension?: string
  diagnosticSessionId?: string
  answered: boolean
}

export interface DiagnosticAssessment {
  status: 'estimated' | 'insufficient_evidence' | string
  estimatedScore: number | null
  confidence: number
  answeredCount: number
  manualAdjustment?: number
  lastAssessedAt?: string
}

export interface DiagnosticSession {
  sessionId: string
  learnerId: number
  status: 'active' | 'completed' | 'failed' | string
  totalQuestions: number
  answeredQuestions: number
  questionsPerDimension: number
  questions: DiagnosticQuestion[]
  assessments: Record<string, DiagnosticAssessment>
}

export interface DiagnosticAnswerResult {
  success: boolean
  alreadyAnswered?: boolean
  isCorrect: boolean | null
  score: number | null
  abilityDimension?: string
  sessionComplete?: boolean
  assessments?: Record<string, DiagnosticAssessment>
}

export const diagnosticApi = {
  createSession(learnerId: number, questionsPerDimension = 2): Promise<DiagnosticSession> {
    return http.post<DiagnosticSession>('/diagnostic/sessions', {
      learnerId,
      questionsPerDimension,
    }, { timeout: 120000 })
  },

  getSession(sessionId: string): Promise<DiagnosticSession> {
    return http.get<DiagnosticSession>(`/diagnostic/sessions/${encodeURIComponent(sessionId)}`)
  },

  submitAnswer(
    sessionId: string,
    data: { questionId: string; userAnswer: string[]; timeSpentMs?: number },
  ): Promise<DiagnosticAnswerResult> {
    return http.post<DiagnosticAnswerResult>(
      `/diagnostic/sessions/${encodeURIComponent(sessionId)}/answers`,
      data,
      { timeout: 30000 },
    )
  },
}
