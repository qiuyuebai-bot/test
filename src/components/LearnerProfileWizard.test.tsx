import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { LearnerProfile } from '@/types'
import { renderWithRouter } from '../test/renderPage'

const createSession = vi.fn()

vi.mock('@/api', () => ({
  diagnosticApi: {
    createSession,
    submitAnswer: vi.fn(),
  },
}))

describe('LearnerProfileWizard', () => {
  it('does not overwrite completed diagnostic scores with stale profile values', async () => {
    const learner: LearnerProfile = {
      id: 7,
      realName: '测试学习者',
      educationLevel: '本科',
      major: '计算机科学',
      learningStyle: 'visual',
      theoreticalFoundation: 0,
      programmingAbility: 0,
      algorithmDesign: 0,
      systemArchitecture: 0,
      dataAnalysis: 0,
      engineeringPractice: 0,
      averageAbility: 0,
      knowledgeBlindAreas: [],
      isDataAnonymized: false,
    }
    createSession.mockResolvedValue({
      sessionId: 'completed-session',
      learnerId: learner.id,
      status: 'completed',
      totalQuestions: 12,
      answeredQuestions: 12,
      questionsPerDimension: 2,
      questions: [],
      assessments: {},
    })
    const onSave = vi.fn().mockResolvedValue(learner)
    const { default: LearnerProfileWizard } = await import('./LearnerProfileWizard')
    const user = userEvent.setup()

    renderWithRouter(
      <LearnerProfileWizard isOpen onClose={vi.fn()} learner={learner} onSave={onSave} />,
    )
    await user.click(screen.getByRole('button', { name: /下一步/ }))
    await user.click(screen.getByRole('button', { name: /开始 12 题诊断/ }))
    await screen.findByText('查看系统估算结果')
    await user.click(screen.getByRole('button', { name: /下一步/ }))
    await user.click(screen.getByRole('button', { name: /保存画像/ }))

    const finalPayload = onSave.mock.calls[onSave.mock.calls.length - 1]?.[0]
    expect(finalPayload).not.toHaveProperty('theoreticalFoundation')
    expect(finalPayload).not.toHaveProperty('programmingAbility')
    expect(finalPayload).not.toHaveProperty('algorithmDesign')
    expect(finalPayload).not.toHaveProperty('systemArchitecture')
    expect(finalPayload).not.toHaveProperty('dataAnalysis')
    expect(finalPayload).not.toHaveProperty('engineeringPractice')
  })
})
