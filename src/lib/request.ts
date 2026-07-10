import { keysToCamel, keysToSnake } from './utils'
import { toast } from '../components/toastStore'
import { reportError } from './sentry'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'
const USER_KEY = 'user_info'

const DEFAULT_TIMEOUT = 30000
const LONG_TIMEOUT = 120000

type HTTPMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'

interface RequestOptions {
  method?: HTTPMethod
  body?: unknown
  params?: Record<string, string | number | boolean | undefined>
  headers?: Record<string, string>
  signal?: AbortSignal
  timeout?: number
  silent?: boolean
  skipAuth?: boolean
}

export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
  timestamp: string
}

export interface PagedData<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

export class ApiError extends Error {
  code: number
  data?: unknown
  constructor(code: number, message: string, data?: unknown) {
    super(message)
    this.code = code
    this.data = data
    this.name = 'ApiError'
  }
}

export class NetworkError extends Error {
  constructor(message = '网络连接失败，请检查网络后重试') {
    super(message)
    this.name = 'NetworkError'
  }
}

export class TimeoutError extends Error {
  constructor(message = '请求超时，请稍后重试') {
    super(message)
    this.name = 'TimeoutError'
  }
}

function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
}

export function setUserInfo(user: { user_id: number; username: string; role: string }): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function getUserInfo(): { userId: number; username: string; role: string } | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return keysToCamel(JSON.parse(raw))
  } catch {
    return null
  }
}

export function clearAuth(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function isAuthenticated(): boolean {
  return !!getAccessToken()
}

export function getUserRole(): string | null {
  const info = getUserInfo()
  return info?.role ?? null
}

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(API_BASE_URL + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value))
      }
    })
  }
  return url.pathname + url.search
}

let isRefreshing = false
let refreshPromise: Promise<boolean> | null = null

async function refreshTokenRequest(): Promise<boolean> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise
  }

  isRefreshing = true
  refreshPromise = (async () => {
    const refresh = getRefreshToken()
    if (!refresh) return false
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 10000)
      const resp = await fetch(API_BASE_URL + '/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
        signal: controller.signal,
      })
      clearTimeout(timeoutId)
      const data: ApiResponse<{ access_token: string; refresh_token: string }> = await resp.json()
      if (data.code === 200 && data.data) {
        setTokens(data.data.access_token, data.data.refresh_token)
        return true
      }
      return false
    } catch {
      return false
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()

  return refreshPromise
}

function doFetch(url: string, config: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  const signal = config.signal
  if (signal) {
    if (signal.aborted) {
      clearTimeout(timeoutId)
      return Promise.reject(new DOMException('Aborted', 'AbortError'))
    }
    signal.addEventListener('abort', () => controller.abort(), { once: true })
  }

  return fetch(url, { ...config, signal: controller.signal }).finally(() => {
    clearTimeout(timeoutId)
  })
}

function handleAuthFailure(silent: boolean) {
  clearAuth()
  window.dispatchEvent(new CustomEvent('auth:logout'))
  if (!silent) {
    toast.warning('登录已过期', '请重新登录')
  }
}

async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    method = 'GET',
    body,
    params,
    headers = {},
    signal,
    timeout = method === 'GET' ? DEFAULT_TIMEOUT : LONG_TIMEOUT,
    silent = false,
    skipAuth = false,
  } = options

  const url = buildUrl(path, params)

  const finalHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...headers,
  }

  if (!skipAuth) {
    const token = getAccessToken()
    if (token) {
      finalHeaders['Authorization'] = `Bearer ${token}`
    }
  }

  const config: RequestInit = {
    method,
    headers: finalHeaders,
    signal,
  }

  if (body !== undefined && method !== 'GET') {
    if (body instanceof FormData) {
      delete finalHeaders['Content-Type']
      config.body = body
    } else {
      config.body = JSON.stringify(keysToSnake(body))
    }
  }

  let response: Response
  try {
    response = await doFetch(url, config, timeout)
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      if (signal?.aborted) {
        throw err
      }
      throw new TimeoutError()
    }
    if (!silent) {
      toast.error('网络错误', '无法连接到服务器，请检查网络连接')
    }
    const networkErr = new NetworkError()
    if (!silent) {
      reportError(networkErr, {
        tags: { kind: 'network', endpoint: path },
        extra: { method, url, cause: String(err) },
      })
    }
    throw networkErr
  }

  if (response.status === 401 && !skipAuth && !path.endsWith('/auth/login') && !path.endsWith('/auth/refresh')) {
    const refreshed = await refreshTokenRequest()
    if (refreshed) {
      const newToken = getAccessToken()
      if (newToken) {
        finalHeaders['Authorization'] = `Bearer ${newToken}`
      }
      if (body !== undefined && method !== 'GET' && !(body instanceof FormData)) {
        config.body = JSON.stringify(keysToSnake(body))
      }
      try {
        response = await doFetch(url, { ...config, headers: finalHeaders }, timeout)
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          if (signal?.aborted) throw err
          throw new TimeoutError()
        }
        if (!silent) {
          toast.error('网络错误', '无法连接到服务器，请检查网络连接')
        }
        throw new NetworkError()
      }
      if (response.status === 401) {
        handleAuthFailure(silent)
        throw new ApiError(401, '登录已过期，请重新登录')
      }
    } else {
      handleAuthFailure(silent)
      throw new ApiError(401, '登录已过期，请重新登录')
    }
  }

  if (response.status === 403) {
    if (!silent) {
      toast.error('没有权限', '您没有执行此操作的权限')
    }
    throw new ApiError(403, '权限不足')
  }

  if (response.status >= 500) {
    if (!silent) {
      toast.error('服务器错误', '服务器处理异常，请稍后重试')
    }
    const err = new ApiError(response.status, '服务器内部错误')
    if (!silent) {
      reportError(err, {
        tags: { httpStatus: response.status, endpoint: path },
        extra: { method, url },
      })
    }
    throw err
  }

  const contentType = response.headers.get('content-type') || ''

  if (!contentType.includes('application/json')) {
    if (!response.ok) {
      throw new ApiError(response.status, response.statusText || '请求失败')
    }
    return response.blob() as unknown as T
  }

  const text = await response.text()
  let data: ApiResponse<unknown>

  try {
    data = text ? JSON.parse(text) : { code: response.status, message: response.statusText, data: null, timestamp: '' }
  } catch {
    if (!response.ok) {
      throw new ApiError(response.status, response.statusText || '请求失败')
    }
    return text as unknown as T
  }

  if (data.code !== 200 && data.code !== 201) {
    if (data.code === 401) {
      handleAuthFailure(silent)
    } else if (data.code === 422) {
      if (!silent) {
        const msg = typeof data.data === 'object' && data.data
          ? Object.values(data.data).flat().join('；')
          : data.message
        toast.error('参数校验失败', msg || '请检查输入内容')
      }
    } else if (!silent && data.code !== 403 && data.code < 500) {
      toast.error('请求失败', data.message)
    }
    throw new ApiError(data.code, data.message, data.data)
  }

  return keysToCamel(data.data) as T
}

export const http = {
  get<T = unknown>(
    path: string,
    params?: Record<string, string | number | boolean | undefined>,
    options?: Omit<RequestOptions, 'method' | 'body' | 'params'>,
  ): Promise<T> {
    return request<T>(path, { ...options, method: 'GET', params })
  },
  post<T = unknown>(
    path: string,
    body?: unknown,
    options?: Omit<RequestOptions, 'method' | 'body'>,
  ): Promise<T> {
    return request<T>(path, { ...options, method: 'POST', body })
  },
  put<T = unknown>(
    path: string,
    body?: unknown,
    options?: Omit<RequestOptions, 'method' | 'body'>,
  ): Promise<T> {
    return request<T>(path, { ...options, method: 'PUT', body })
  },
  delete<T = unknown>(
    path: string,
    options?: Omit<RequestOptions, 'method' | 'body'>,
  ): Promise<T> {
    return request<T>(path, { ...options, method: 'DELETE' })
  },
  patch<T = unknown>(
    path: string,
    body?: unknown,
    options?: Omit<RequestOptions, 'method' | 'body'>,
  ): Promise<T> {
    return request<T>(path, { ...options, method: 'PATCH', body })
  },
}

export function createEventSource(
  path: string,
  params?: Record<string, string | number | boolean | undefined>,
): EventSource {
  const allParams: Record<string, string> = {}
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        allParams[key] = String(value)
      }
    })
  }
  const url = buildUrl(path, allParams)
  return new EventSource(url)
}
