import { describe, it, expect } from 'vitest'
import {
  loginSchema,
  changePasswordSchema,
  createLearnerSchema,
  uploadKnowledgeSchema,
  generateResourcesSchema,
  searchSchema,
} from './index'

const valid = (schema: { safeParse: (v: unknown) => { success: boolean } }, value: unknown) =>
  schema.safeParse(value).success

describe('loginSchema', () => {
  it('accepts a valid username/password', () => {
    expect(valid(loginSchema, { username: 'alice', password: 'secret1' })).toBe(true)
  })
  it('rejects username shorter than 2 chars', () => {
    expect(valid(loginSchema, { username: 'a', password: 'secret1' })).toBe(false)
  })
  it('rejects password shorter than 6 chars', () => {
    expect(valid(loginSchema, { username: 'alice', password: '12345' })).toBe(false)
  })
  it('rejects username over 50 chars', () => {
    expect(valid(loginSchema, { username: 'a'.repeat(51), password: 'secret1' })).toBe(false)
  })
  it('rejects missing fields', () => {
    expect(valid(loginSchema, { username: '', password: '' })).toBe(false)
  })
})

describe('changePasswordSchema', () => {
  const ok = {
    oldPassword: 'oldpass1',
    newPassword: 'newPass1',
    confirmPassword: 'newPass1',
  }
  it('accepts matching passwords with letter+digit and >=8 chars', () => {
    expect(valid(changePasswordSchema, ok)).toBe(true)
  })
  it('rejects when newPassword lacks a digit', () => {
    expect(valid(changePasswordSchema, { ...ok, newPassword: 'NoDigits', confirmPassword: 'NoDigits' })).toBe(false)
  })
  it('rejects when newPassword lacks a letter', () => {
    expect(valid(changePasswordSchema, { ...ok, newPassword: '12345678', confirmPassword: '12345678' })).toBe(false)
  })
  it('rejects when newPassword shorter than 8', () => {
    expect(valid(changePasswordSchema, { ...ok, newPassword: 'Ab1', confirmPassword: 'Ab1' })).toBe(false)
  })
  it('rejects when confirmPassword differs from newPassword', () => {
    expect(valid(changePasswordSchema, { ...ok, confirmPassword: 'different1' })).toBe(false)
  })
})

describe('createLearnerSchema', () => {
  const base = {
    realName: '张三',
    educationLevel: 'master',
    major: '计算机科学',
    targetIndustry: 'AI',
  }
  it('accepts the minimal valid payload', () => {
    expect(valid(createLearnerSchema, base)).toBe(true)
  })
  it('coerces graduationYear from string to number and validates range', () => {
    expect(valid(createLearnerSchema, { ...base, graduationYear: '2020' })).toBe(true)
    expect(valid(createLearnerSchema, { ...base, graduationYear: '1989' })).toBe(false)
    expect(valid(createLearnerSchema, { ...base, graduationYear: '2036' })).toBe(false)
  })
  it('rejects ability scores out of 0-100', () => {
    expect(valid(createLearnerSchema, { ...base, programmingAbility: 101 })).toBe(false)
    expect(valid(createLearnerSchema, { ...base, programmingAbility: -1 })).toBe(false)
  })
  it('rejects preferredDifficulty out of 1-5', () => {
    expect(valid(createLearnerSchema, { ...base, preferredDifficulty: 6 })).toBe(false)
    expect(valid(createLearnerSchema, { ...base, preferredDifficulty: 0 })).toBe(false)
  })
  it('rejects realName shorter than 2', () => {
    expect(valid(createLearnerSchema, { ...base, realName: '张' })).toBe(false)
  })
  it('rejects missing targetIndustry', () => {
    expect(valid(createLearnerSchema, { realName: '张三', educationLevel: 'master', major: 'cs' })).toBe(false)
  })
})

describe('uploadKnowledgeSchema', () => {
  it('accepts valid payload', () => {
    expect(valid(uploadKnowledgeSchema, {
      title: '深度学习导论', industry: 'AI', content: 'a'.repeat(10),
    })).toBe(true)
  })
  it('rejects content shorter than 10 chars', () => {
    expect(valid(uploadKnowledgeSchema, {
      title: 't', industry: 'AI', content: 'short',
    })).toBe(false)
  })
  it('rejects content over 100000 chars', () => {
    expect(valid(uploadKnowledgeSchema, {
      title: 't1', industry: 'AI', content: 'a'.repeat(100001),
    })).toBe(false)
  })
})

describe('generateResourcesSchema', () => {
  it('accepts valid payload', () => {
    expect(valid(generateResourcesSchema, { learnerId: 1, targetTopic: 'CNN' })).toBe(true)
  })
  it('coerces learnerId from string and rejects non-positive', () => {
    expect(valid(generateResourcesSchema, { learnerId: '1', targetTopic: 'CNN' })).toBe(true)
    expect(valid(generateResourcesSchema, { learnerId: 0, targetTopic: 'CNN' })).toBe(false)
  })
  it('rejects targetTopic shorter than 2', () => {
    expect(valid(generateResourcesSchema, { learnerId: 1, targetTopic: 'C' })).toBe(false)
  })
})

describe('searchSchema', () => {
  it('accepts valid query', () => {
    expect(valid(searchSchema, { query: '神经网络' })).toBe(true)
  })
  it('rejects empty query', () => {
    expect(valid(searchSchema, { query: '' })).toBe(false)
  })
  it('rejects query over 500 chars', () => {
    expect(valid(searchSchema, { query: 'a'.repeat(501) })).toBe(false)
  })
  it('coerces and validates topK within 1-50', () => {
    expect(valid(searchSchema, { query: 'q', topK: '10' })).toBe(true)
    expect(valid(searchSchema, { query: 'q', topK: 51 })).toBe(false)
  })
  it('rejects minSimilarity out of 0-1', () => {
    expect(valid(searchSchema, { query: 'q', minSimilarity: 1.5 })).toBe(false)
  })
})
