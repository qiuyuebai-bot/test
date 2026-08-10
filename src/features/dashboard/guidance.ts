import type { LearnerProfile } from '@/types'
import type { GuidanceStage } from '@/api/dashboard'

export interface GuidanceFacts {
  profile: LearnerProfile | null
  hasDiagnosis: boolean
  resourceCount: number
  answerCount: number
}

export function isProfileComplete(profile: LearnerProfile | null): boolean {
  return Boolean(profile?.realName && profile.educationLevel && profile.major)
}

export function getGuidanceStage(facts: GuidanceFacts): GuidanceStage {
  if (!isProfileComplete(facts.profile)) return 'profile'
  if (!facts.hasDiagnosis) return 'diagnosis'
  if (facts.resourceCount === 0) return 'resource'
  if (facts.answerCount === 0) return 'guidance'
  return 'feedback'
}

export function getGuidanceStageLabel(stage: GuidanceStage): string {
  return {
    profile: '完善学习者画像',
    diagnosis: '开始首次诊断',
    resource: '生成首份个性化资源',
    guidance: '开始自适应导学',
    feedback: '查看反馈并进入下一知识点',
  }[stage]
}
