import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense, useEffect } from 'react'
import Layout from './components/Layout'
import ToastContainer from './components/Toast'
import { PageSkeleton } from './components/Skeleton'
import { ProtectedRoute, PublicOnlyRoute } from './components/ProtectedRoute'
import { useStore } from './store'
import { routeLoaders } from './lib/routePrefetch'

const Login = lazy(routeLoaders['/login'])
const OnboardingName = lazy(routeLoaders['/onboarding/name'])
const Dashboard = lazy(routeLoaders['/dashboard'])
const MultiAgentVisualization = lazy(routeLoaders['/multi-agent'])
const TaskEvidenceWorkspace = lazy(routeLoaders['/multi-agent/tasks/:taskId/evidence'])
const LearnerProfile = lazy(routeLoaders['/profile'])
const KnowledgeBase = lazy(routeLoaders['/knowledge-base'])
const ResourceGeneration = lazy(routeLoaders['/resources'])
const ResourceReader = lazy(routeLoaders['/resources/:resourceId/read'])
const LearningReport = lazy(routeLoaders['/report'])
const AdaptiveGuidance = lazy(routeLoaders['/guidance'])
const SystemTest = lazy(routeLoaders['/monitoring'])
const MetricsDashboard = lazy(routeLoaders['/metrics'])
const AdminOpsOverview = lazy(routeLoaders['/ops'])
const CareerTraining = lazy(routeLoaders['/career-training'])

function PageFallback() {
  return <PageSkeleton />
}

function App() {
  const isDarkMode = useStore((s) => s.isDarkMode)

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [isDarkMode])

  return (
    <BrowserRouter>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route
            path="/login"
            element={
              <PublicOnlyRoute>
                <Login />
              </PublicOnlyRoute>
            }
          />
          <Route
            path="/onboarding/name"
            element={
              <ProtectedRoute>
                <OnboardingName />
              </ProtectedRoute>
            }
          />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route
              path="ops"
              element={
                <ProtectedRoute roles={['admin']}>
                  <AdminOpsOverview />
                </ProtectedRoute>
              }
            />
            <Route
              path="multi-agent"
              element={
                <ProtectedRoute roles={['admin']}>
                  <MultiAgentVisualization />
                </ProtectedRoute>
              }
            />
            <Route
              path="multi-agent/tasks/:taskId/evidence"
              element={
                <ProtectedRoute roles={['admin']}>
                  <TaskEvidenceWorkspace />
                </ProtectedRoute>
              }
            />
            <Route path="profile" element={<LearnerProfile />} />
            <Route
              path="knowledge-base"
              element={
                <ProtectedRoute roles={['admin']}>
                  <KnowledgeBase />
                </ProtectedRoute>
              }
            />
            <Route path="resources" element={<ResourceGeneration />} />
            <Route path="resources/:resourceId/read" element={<ResourceReader />} />
            <Route path="report" element={<LearningReport />} />
            <Route path="guidance" element={<AdaptiveGuidance />} />
            <Route
              path="career-training"
              element={
                <ProtectedRoute roles={['admin']}>
                  <CareerTraining />
                </ProtectedRoute>
              }
            />
            <Route
              path="career-training/:tab"
              element={
                <ProtectedRoute roles={['admin']}>
                  <CareerTraining />
                </ProtectedRoute>
              }
            />
            <Route
              path="enterprise"
              element={
                <ProtectedRoute roles={['admin']}>
                  <Navigate to="/career-training/position" replace />
                </ProtectedRoute>
              }
            />
            <Route path="privacy" element={<Navigate to="/dashboard" replace />} />
            <Route
              path="monitoring"
              element={
                <ProtectedRoute roles={['admin']}>
                  <SystemTest />
                </ProtectedRoute>
              }
            />
            <Route path="test" element={<Navigate to="/monitoring" replace />} />
            <Route path="deployment" element={<Navigate to="/dashboard" replace />} />
            <Route
              path="metrics"
              element={
                <ProtectedRoute roles={['admin']}>
                  <MetricsDashboard />
                </ProtectedRoute>
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
      <ToastContainer />
    </BrowserRouter>
  )
}

export default App
