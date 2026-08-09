import { describe, it, expect } from 'vitest'
import { toCamelCase, toSnakeCase, keysToCamel, keysToSnake } from './utils'

describe('toCamelCase', () => {
  it('converts snake_case to camelCase', () => {
    expect(toCamelCase('user_id')).toBe('userId')
    expect(toCamelCase('first_name')).toBe('firstName')
  })

  it('handles consecutive underscores by converting each', () => {
    expect(toCamelCase('a_b_c')).toBe('aBC')
    expect(toCamelCase('name')).toBe('name')
    expect(toCamelCase('already')).toBe('already')
  })
})

describe('toSnakeCase', () => {
  it('converts camelCase to snake_case', () => {
    expect(toSnakeCase('userId')).toBe('user_id')
    expect(toSnakeCase('firstName')).toBe('first_name')
  })

  it('leaves already-snake strings unchanged', () => {
    expect(toSnakeCase('name')).toBe('name')
  })
})

describe('keysToCamel', () => {
  it('converts top-level snake_case keys', () => {
    const input = { user_id: 1, first_name: 'a' }
    expect(keysToCamel(input)).toEqual({ userId: 1, firstName: 'a' })
  })

  it('converts nested object keys recursively', () => {
    const input = { outer_key: { inner_key: 'v' } }
    expect(keysToCamel(input)).toEqual({ outerKey: { innerKey: 'v' } })
  })

  it('converts keys inside arrays element-wise', () => {
    const input = [{ user_id: 1 }, { user_id: 2 }]
    expect(keysToCamel(input)).toEqual([{ userId: 1 }, { userId: 2 }])
  })

  it('returns null/undefined/primitives unchanged', () => {
    expect(keysToCamel(null)).toBeNull()
    expect(keysToCamel(undefined)).toBeUndefined()
    expect(keysToCamel(42)).toBe(42)
    expect(keysToCamel('str')).toBe('str')
  })
})

describe('keysToSnake', () => {
  it('converts top-level camelCase keys', () => {
    const input = { userId: 1, firstName: 'a' }
    expect(keysToSnake(input)).toEqual({ user_id: 1, first_name: 'a' })
  })

  it('converts nested object keys recursively', () => {
    const input = { outerKey: { innerKey: 'v' } }
    expect(keysToSnake(input)).toEqual({ outer_key: { inner_key: 'v' } })
  })

  it('round-trips camel -> snake -> camel including arrays', () => {
    const arr = [{ userId: 1 }, { userId: 2 }]
    expect(keysToSnake(arr)).toEqual([{ user_id: 1 }, { user_id: 2 }])
    expect(keysToCamel(keysToSnake(arr))).toEqual(arr)

    const original = { userId: 1, profile: { firstName: 'a' } }
    const snake = keysToSnake(original)
    const back = keysToCamel(snake)
    expect(back).toEqual(original)
  })
})
