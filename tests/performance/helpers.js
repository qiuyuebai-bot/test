/**
 * k6 性能测试辅助函数
 * 提供登录、认证请求、响应校验等通用功能
 */
import http from 'k6/http'
import { check, sleep } from 'k6'
import { BASE_URL, API_PREFIX, ADMIN } from './config.js'

const TOKEN_KEY = 'perf_access_token'

/**
 * 登录并缓存 access_token（每个 VU 独立，避免重复登录）
 * 在 setup 阶段调用一次，token 通过VuData传递
 */
export function login() {
  const url = `${BASE_URL}${API_PREFIX}/auth/login`
  const payload = JSON.stringify({
    username: ADMIN.username,
    password: ADMIN.password,
  })
  const params = {
    headers: { 'Content-Type': 'application/json' },
    timeout: '30s',
  }

  const res = http.post(url, payload, params)

  if (!check(res, {
    'login status 200': (r) => r.status === 200,
    'login body code 200': (r) => {
      try {
        return JSON.parse(r.body).code === 200
      } catch {
        return false
      }
    },
  })) {
    console.error(`登录失败: status=${res.status}, body=${res.body}`)
    return null
  }

  try {
    const body = JSON.parse(res.body)
    return body.data.access_token
  } catch {
    console.error('登录响应解析失败')
    return null
  }
}

/**
 * 构造认证请求头
 */
export function authHeaders(token, extra = {}) {
  return {
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
      ...extra,
    },
  }
}

/**
 * 执行单个端点请求
 * @param {string} name - 端点名（对应 config.js 中的 key）
 * @param {object} endpoint - 端点定义
 * @param {string|null} token - access_token
 * @returns {object} k6 response
 */
export function hitEndpoint(name, endpoint, token) {
  const url = `${BASE_URL}${endpoint.path}`
  const needsAuth = endpoint.authRequired && token
  const params = needsAuth
    ? authHeaders(token)
    : { headers: { 'Content-Type': 'application/json' } }

  let res
  if (endpoint.method === 'GET') {
    res = http.get(url, params)
  } else if (endpoint.method === 'POST') {
    const body = endpoint.body ? JSON.stringify(endpoint.body()) : ''
    res = http.post(url, body, params)
  } else {
    res = http.request(endpoint.method, url, null, params)
  }

  check(res, {
    [`${name} status 200`]: (r) => r.status === 200,
  })

  return res
}

/**
 * 按权重随机选择端点
 * @param {object} endpoints - 端点字典
 * @returns {object} { name, endpoint }
 */
export function pickWeightedEndpoint(endpoints) {
  const entries = Object.entries(endpoints)
  const totalWeight = entries.reduce((sum, [, ep]) => sum + ep.weight, 0)
  let random = Math.random() * totalWeight

  for (const [name, ep] of entries) {
    random -= ep.weight
    if (random <= 0) {
      return { name, endpoint: ep }
    }
  }
  return { name: entries[0][0], endpoint: entries[0][1] }
}
