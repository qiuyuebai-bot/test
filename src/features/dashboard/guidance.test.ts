import { describe, expect, it } from 'vitest'
import { getGuidanceStage, getGuidanceStageLabel, isProfileComplete } from './guidance'

const completeProfile = {
  realName: '学习者',
  educationLevel: '本科',
  major: '计算机科学',
} as never

describe('dashboard guidance state machine', () => {
  it.each([
    ['profile', { profile: null, hasDiagnosis: false, resourceCount: 0, answerCount: 0 }],
    [
      'profile',
      {
        profile: { realName: '', educationLevel: '本科', major: '计算机科学' },
        hasDiagnosis: true,
        resourceCount: 2,
        answerCount: 1,
      },
    ],
    [
      'diagnosis',
      { profile: completeProfile, hasDiagnosis: false, resourceCount: 0, answerCount: 0 },
    ],
    [
      'resource',
      { profile: completeProfile, hasDiagnosis: true, resourceCount: 0, answerCount: 0 },
    ],
    [
      'guidance',
      { profile: completeProfile, hasDiagnosis: true, resourceCount: 2, answerCount: 0 },
    ],
    [
      'feedback',
      { profile: completeProfile, hasDiagnosis: true, resourceCount: 2, answerCount: 1 },
    ],
  ] as const)('resolves the %s stage from business facts', (expected, facts) => {
    expect(getGuidanceStage(facts as never)).toBe(expected)
  })

  it('does not consider a profile complete without the required identity fields', () => {
    expect(isProfileComplete(null)).toBe(false)
    expect(isProfileComplete({ realName: 'A', educationLevel: '', major: 'CS' } as never)).toBe(
      false,
    )
    expect(isProfileComplete(completeProfile)).toBe(true)
  })

  it('provides an actionable label for every stage', () => {
    expect(getGuidanceStageLabel('feedback')).toContain('反馈')
  })
})
