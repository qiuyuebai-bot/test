import { describe, expect, it } from 'vitest'
import type { TutoringQuestion } from '@/api/core'
import { guidanceReducer, initialGuidanceState } from './guidanceReducer'

const question = (id: string, difficulty = 2): TutoringQuestion => ({
  id,
  type: 'single',
  topic: 'CNN',
  question: `Question ${id}`,
  options: ['A', 'B'],
  difficulty,
  generationMethod: 'deterministic_fallback',
})

function answeringState() {
  return guidanceReducer(initialGuidanceState, {
    type: 'hydrated',
    questions: [question('q1')],
    sessionConfig: { topic: 'CNN', questionCount: 2, sessionId: 'session_test' },
  })
}

describe('guidanceReducer', () => {
  it('stores the topic resolved by the backend when the session started without one', () => {
    const generated = guidanceReducer(initialGuidanceState, {
      type: 'generation_succeeded',
      mode: 'start',
      questions: [question('q1')],
      sessionConfig: { topic: '', questionCount: 5 },
    })

    const updated = guidanceReducer(generated, { type: 'session_topic_updated', topic: 'CNN' })

    expect(updated.sessionConfig?.topic).toBe('CNN')
  })

  it('moves from submitting to feedback and records the result', () => {
    const submitting = guidanceReducer(answeringState(), { type: 'submit_started' })
    const result = { isCorrect: true, score: 100 }

    const feedback = guidanceReducer(submitting, {
      type: 'submit_succeeded',
      result,
      completed: false,
      nextDifficulty: 3,
    })

    expect(feedback.phase).toBe('feedback')
    expect(feedback.showResult).toBe(true)
    expect(feedback.submitResult).toEqual(result)
    expect(feedback.correctCount).toBe(1)
    expect(feedback.pendingNextDifficulty).toBe(3)
  })

  it('keeps the current feedback visible when the next question prefetch fails', () => {
    const feedback = guidanceReducer(
      guidanceReducer(answeringState(), { type: 'submit_started' }),
      {
        type: 'submit_succeeded',
        result: { isCorrect: false, score: 0 },
        completed: false,
        nextDifficulty: 1,
      },
    )
    const preparing = guidanceReducer(feedback, { type: 'prefetch_started', difficulty: 1 })
    const failed = guidanceReducer(preparing, { type: 'prefetch_failed', error: 'network error' })

    expect(preparing.phase).toBe('preparingNext')
    expect(failed.phase).toBe('feedback')
    expect(failed.showResult).toBe(true)
    expect(failed.submitResult).toEqual(feedback.submitResult)
    expect(failed.nextQuestionError).toBe('network error')
  })

  it('appends a prefetched question and advances without carrying the previous answer', () => {
    const feedback = guidanceReducer(
      guidanceReducer(answeringState(), { type: 'submit_started' }),
      {
        type: 'submit_succeeded',
        result: { isCorrect: true, score: 100 },
        completed: false,
        nextDifficulty: 3,
      },
    )
    const prepared = guidanceReducer(feedback, {
      type: 'prefetch_succeeded',
      questions: [question('q2', 3)],
      generationMethod: 'deepseek',
    })
    const next = guidanceReducer(prepared, { type: 'advance_question' })

    expect(prepared.questions.map((item) => item.id)).toEqual(['q1', 'q2'])
    expect(next.phase).toBe('answering')
    expect(next.currentQuestion).toBe(1)
    expect(next.selectedAnswers).toEqual([])
    expect(next.showResult).toBe(false)
    expect(next.submitResult).toBeNull()
  })

  it('clears the active session when the learner exits', () => {
    const active = answeringState()
    const exited = guidanceReducer(active, { type: 'exit_session' })

    expect(exited.phase).toBe('ready')
    expect(exited.questions).toEqual([])
    expect(exited.sessionConfig).toBeNull()
    expect(exited.currentQuestion).toBe(0)
  })
})
