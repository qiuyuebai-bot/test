/**
 * 冒烟测试 - 验证系统在最小负载下正常工作
 *
 * 运行:
 *   k6 run tests/performance/smoke.js
 *   docker run --rm -i --network host grafana/k6 run - < tests/performance/smoke.js
 *
 * 预期: 所有端点返回 200，p95 < 1s
 */
import { check } from 'k6'
import { login, hitEndpoint, authHeaders } from './helpers.js'
import { BASE_URL, ENDPOINTS, COMMON_THRESHOLDS } from './config.js'

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: COMMON_THRESHOLDS,
  tags: { scenario: 'smoke' },
}

export function setup() {
  const token = login()
  if (!token) {
    throw new Error('冒烟测试前置登录失败，终止')
  }
  return { token }
}

export default function (data) {
  // 逐个验证所有端点
  for (const [name, endpoint] of Object.entries(ENDPOINTS)) {
    const res = hitEndpoint(name, endpoint, data.token)
    check(res, {
      [`${name} returns valid JSON`]: (r) => {
        try {
          const body = JSON.parse(r.body)
          return body.code !== undefined
        } catch {
          return false
        }
      },
    })
  }
}
