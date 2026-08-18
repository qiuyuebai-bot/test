import { keysToCamel, keysToSnake, toSnakeCase } from './utils'
import { toast } from '../components/toastStore'
import { reportError } from './sentry'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const USER_KEY = 'user_info'

// Access tokens live only for the current page session. Refresh credentials are
// kept in an HttpOnly cookie by the backend and are never readable by JS.
let accessToken: string | null = null

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

export function getAccessToken(): string | null {
  return accessToken
}

function getRefreshToken(): string | null {
  return null
}

export function setTokens(nextAccessToken: string, refreshToken: string): void {
  void refreshToken
  accessToken = nextAccessToken
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
  accessToken = null
  localStorage.removeItem(USER_KEY)
}

export function isAuthenticated(): boolean {
  return !!getAccessToken() || !!getUserInfo()
}

export function getUserRole(): string | null {
  const info = getUserInfo()
  return info?.role ?? null
}

export function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(API_BASE_URL + path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        // query 参数 key 统一转 snake_case，与后端 FastAPI 参数命名及 POST body 的 keysToSnake 行为一致
        url.searchParams.append(toSnakeCase(key), String(value))
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
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 10000)
      const refreshConfig: RequestInit = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        signal: controller.signal,
      }
      if (refresh) {
        refreshConfig.body = JSON.stringify({ refresh_token: refresh })
      }
      const resp = await fetch(API_BASE_URL + '/auth/refresh', {
        ...refreshConfig,
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
  const onAbort = () => controller.abort()
  if (signal) {
    if (signal.aborted) {
      clearTimeout(timeoutId)
      return Promise.reject(new DOMException('Aborted', 'AbortError'))
    }
    signal.addEventListener('abort', onAbort, { once: true })
  }

  return fetch(url, { ...config, credentials: 'include', signal: controller.signal }).finally(() => {
    clearTimeout(timeoutId)
    if (signal) {
      signal.removeEventListener('abort', onAbort)
    }
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
    const contentType = response.headers.get('content-type') || ''
    if (!contentType.includes('application/json')) {
      const unavailable = new NetworkError('后端服务暂不可用，请确认服务已启动')
      if (!silent) {
        toast.error('后端服务不可用', unavailable.message)
        reportError(unavailable, {
          tags: { kind: 'backend_unavailable', httpStatus: response.status, endpoint: path },
          extra: { method, url },
        })
      }
      throw unavailable
    }
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
    params?: Record<string, string | number | boolean | undefined>,
    options?: Omit<RequestOptions, 'method' | 'body'>,
  ): Promise<T> {
    return request<T>(path, { ...options, method: 'DELETE', params })
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
