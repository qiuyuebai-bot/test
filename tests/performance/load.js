/**
 * 负载测试 - 模拟正常日常流量
 *
 * 运行:
 *   k6 run tests/performance/load.js
 *   docker run --rm -i --network host grafana/k6 run - < tests/performance/load.js
 *
 * 场景: 20 VU 持续 3 分钟，按权重混合调用所有端点
 * 预期: p95 < 500ms，错误率 < 1%
 */
import { sleep } from 'k6'
import { login, hitEndpoint, pickWeightedEndpoint } from './helpers.js'
import { ENDPOINTS, COMMON_THRESHOLDS } from './config.js'

export const options = {
  stages: [
    { duration: '30s', target: 20 },
    { duration: '2m', target: 20 },
    { duration: '30s', target: 0 },
  ],
  thresholds: COMMON_THRESHOLDS,
  tags: { scenario: 'load' },
}

export function setup() {
  const token = login()
  if (!token) {
    throw new Error('负载测试前置登录失败，终止')
  }
  return { token }
}

export default function (data) {
  const { name, endpoint } = pickWeightedEndpoint(ENDPOINTS)
  hitEndpoint(name, endpoint, data.token)
  sleep(0.5 + Math.random() * 1)
}
