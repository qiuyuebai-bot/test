/**
 * 压力测试 - 逐步加压直到系统出现瓶颈
 *
 * 运行:
 *   k6 run tests/performance/stress.js
 *   docker run --rm -i --network host grafana/k6 run - < tests/performance/stress.js
 *
 * 场景: 从 10 VU 阶梯加压至 200 VU，寻找系统拐点
 * 预期: 发现错误率 > 5% 或 p95 > 2s 的临界点
 */
import { sleep } from 'k6'
import { login, hitEndpoint, pickWeightedEndpoint } from './helpers.js'
import { ENDPOINTS, RELAXED_THRESHOLDS } from './config.js'

export const options = {
  stages: [
    { duration: '1m', target: 10 },
    { duration: '1m', target: 50 },
    { duration: '1m', target: 100 },
    { duration: '1m', target: 150 },
    { duration: '1m', target: 200 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    ...RELAXED_THRESHOLDS,
    // 压力测试允许更高的错误率，但仍需监控
    http_req_failed: ['rate<0.10'],
  },
  tags: { scenario: 'stress' },
}

export function setup() {
  const token = login()
  if (!token) {
    throw new Error('压力测试前置登录失败，终止')
  }
  return { token }
}

export default function (data) {
  const { name, endpoint } = pickWeightedEndpoint(ENDPOINTS)
  hitEndpoint(name, endpoint, data.token)
  sleep(0.2 + Math.random() * 0.5)
}
