type RouteLoader = () => Promise<unknown>

export const routeLoaders = {
  '/login': () => import('../pages/Login'),
  '/onboarding/name': () => import('../pages/OnboardingName'),
  '/dashboard': () => import('../pages/Dashboard'),
  '/ops': () => import('../pages/AdminOpsOverview'),
  '/multi-agent': () => import('../pages/MultiAgentVisualization'),
  '/multi-agent/tasks/:taskId/evidence': () => import('../pages/multi-agent/TaskEvidenceWorkspace'),
  '/profile': () => import('../pages/LearnerProfile'),
  '/knowledge-base': () => import('../pages/KnowledgeBase'),
  '/resources': () => import('../pages/ResourceGeneration'),
  '/report': () => import('../pages/LearningReport'),
  '/guidance': () => import('../pages/AdaptiveGuidance'),
  '/monitoring': () => import('../pages/SystemTest'),
  '/metrics': () => import('../pages/MetricsDashboard'),
  '/career-training': () => import('../pages/CareerTraining'),
  '/career-training/position': () => import('../pages/CareerTraining'),
} satisfies Record<string, RouteLoader>

const pendingPrefetches = new Map<string, Promise<unknown>>()

function canPrefetch(): boolean {
  if (typeof navigator === 'undefined') return false
  const connection = (navigator as Navigator & {
    connection?: { saveData?: boolean; effectiveType?: string }
  }).connection
  return !connection?.saveData && connection?.effectiveType !== 'slow-2g' && connection?.effectiveType !== '2g'
}

export function prefetchRoute(path: string): Promise<unknown> | undefined {
  const loader = routeLoaders[path as keyof typeof routeLoaders]
  if (!loader || !canPrefetch()) return undefined

  const pending = pendingPrefetches.get(path)
  if (pending) return pending

  const request = loader()
    .catch(() => undefined)
    .finally(() => pendingPrefetches.delete(path))
  pendingPrefetches.set(path, request)
  return request
}
