export function toCamelCase(str: string): string {
  return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

export interface DebouncedFunction<T extends (...args: never[]) => void> {
  (...args: Parameters<T>): void
  cancel: () => void
}

export function debounce<T extends (...args: never[]) => void>(
  fn: T,
  delayMs: number,
): DebouncedFunction<T> {
  let timer: ReturnType<typeof setTimeout> | null = null
  const debounced = ((...args: Parameters<T>) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn(...args)
    }, delayMs)
  }) as DebouncedFunction<T>
  debounced.cancel = () => {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }
  return debounced
}

export function toSnakeCase(str: string): string {
  return str.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)
}

export function keysToCamel<T = unknown>(obj: unknown): T {
  if (obj === null || obj === undefined) return obj as T
  if (Array.isArray(obj)) return obj.map((v) => keysToCamel(v)) as unknown as T
  if (typeof obj !== 'object') return obj as T

  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    result[toCamelCase(key)] = keysToCamel(value)
  }
  return result as T
}

export function keysToSnake<T = unknown>(obj: unknown): T {
  if (obj === null || obj === undefined) return obj as T
  if (Array.isArray(obj)) return obj.map((v) => keysToSnake(v)) as unknown as T
  if (typeof obj !== 'object') return obj as T

  const result: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    result[toSnakeCase(key)] = keysToSnake(value)
  }
  return result as T
}
