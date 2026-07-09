/**
 * 突发流量测试 - 模拟瞬时高并发冲击
 *
 * 运行:
 *   k6 run tests/performance/spike.js
 *   docker run --rm -i --network host grafana/k6 run - < tests/performance/spike.js
 *
 * 场景: 5s 内从 0 飙升到 100 VU，维持 30s 后骤降
 * 预期: 系统不崩溃，错误率 < 10%，恢复后正常
 */
import { sleep } from 'k6'
import { login, hitEndpoint, pickWeightedEndpoint } from './helpers.js'
import { ENDPOINTS, RELAXED_THRESHOLDS } from './config.js'

export const options = {
  stages: [
    { duration: '5s', target: 100 },
    { duration: '30s', target: 100 },
    { duration: '5s', target: 0 },
    { duration: '30s', target: 10 },
    { duration: '10s', target: 0 },
  ],
  thresholds: {
    ...RELAXED_THRESHOLDS,
    http_req_failed: ['rate<0.10'],
  },
  tags: { scenario: 'spike' },
}

export function setup() {
  const token = login()
  if (!token) {
    throw new Error('突发测试前置登录失败，终止')
  }
  return { token }
}

export default function (data) {
  const { name, endpoint } = pickWeightedEndpoint(ENDPOINTS)
  hitEndpoint(name, endpoint, data.token)
  sleep(0.1 + Math.random() * 0.3)
}
