/**
 * k6 性能测试共享配置
 *
 * 环境变量（可通过 -e 参数覆盖）:
 *   BASE_URL    后端地址，默认 http://localhost:8000
 *   ADMIN_USER  管理员用户名，默认 admin
 *   ADMIN_PASS  管理员密码，默认 admin123
 *   SCENARIO   场景名（由各脚本指定，此处仅定义默认值）
 */
import http from 'k6/http'

export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000'
export const API_PREFIX = '/api/v1'

export const ADMIN = {
  username: __ENV.ADMIN_USER || 'admin',
  password: __ENV.ADMIN_PASS || 'admin123',
}

/**
 * 核心端点定义
 * weight: 混合场景中的调用权重（占比）
 */
export const ENDPOINTS = {
  health: {
    method: 'GET',
    path: '/health',
    weight: 10,
    authRequired: false,
  },
  login: {
    method: 'POST',
    path: '/api/v1/auth/login',
    weight: 5,
    authRequired: false,
    body: () => ({ username: ADMIN.username, password: ADMIN.password }),
  },
  learners: {
    method: 'GET',
    path: '/api/v1/learners?page=1&page_size=10',
    weight: 15,
    authRequired: true,
  },
  knowledgeDocs: {
    method: 'GET',
    path: '/api/v1/knowledge/docs?page=1&page_size=10',
    weight: 15,
    authRequired: true,
  },
  knowledgeSearch: {
    method: 'POST',
    path: '/api/v1/knowledge/search',
    weight: 10,
    authRequired: true,
    body: () => ({ query: '算法基础', top_k: 5 }),
  },
  agentTasks: {
    method: 'GET',
    path: '/api/v1/agent/tasks?page=1&page_size=10',
    weight: 15,
    authRequired: true,
  },
  reportMetrics: {
    method: 'GET',
    path: '/api/v1/report/metrics',
    weight: 10,
    authRequired: true,
  },
  trainings: {
    method: 'GET',
    path: '/api/v1/trainings?page=1&page_size=10',
    weight: 10,
    authRequired: true,
  },
  tutorQuestions: {
    method: 'GET',
    path: '/api/v1/tutoring/questions?page=1&page_size=10',
    weight: 10,
    authRequired: true,
  },
}

/**
 * 通用阈值（各场景可覆盖）
 * - http_req_failed: 请求失败率 < 1%
 * - http_req_duration p95: 95% 请求在 500ms 内完成
 * - http_req_duration p99: 99% 请求在 1.5s 内完成
 */
export const COMMON_THRESHOLDS = {
  http_req_failed: ['rate<0.01'],
  http_req_duration: ['p(95)<500', 'p(99)<1500'],
}

/**
 * 宽松阈值（用于压力测试/突发测试，允许更高延迟）
 */
export const RELAXED_THRESHOLDS = {
  http_req_failed: ['rate<0.05'],
  http_req_duration: ['p(95)<2000', 'p(99)<5000'],
}
