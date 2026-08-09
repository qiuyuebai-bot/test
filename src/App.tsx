import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense, useEffect } from 'react'
import Layout from './components/Layout'
import ToastContainer from './components/Toast'
import { PageSkeleton } from './components/Skeleton'
import { ProtectedRoute, PublicOnlyRoute } from './components/ProtectedRoute'
import { useStore } from './store'

const Login = lazy(() => import('./pages/Login'))
const OnboardingName = lazy(() => import('./pages/OnboardingName'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const MultiAgentVisualization = lazy(() => import('./pages/MultiAgentVisualization'))
const LearnerProfile = lazy(() => import('./pages/LearnerProfile'))
const KnowledgeBase = lazy(() => import('./pages/KnowledgeBase'))
const ResourceGeneration = lazy(() => import('./pages/ResourceGeneration'))
const LearningReport = lazy(() => import('./pages/LearningReport'))
const AdaptiveGuidance = lazy(() => import('./pages/AdaptiveGuidance'))
const SystemTest = lazy(() => import('./pages/SystemTest'))
const MetricsDashboard = lazy(() => import('./pages/MetricsDashboard'))
const AdminOpsOverview = lazy(() => import('./pages/AdminOpsOverview'))

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
            <Route path="profile" element={<LearnerProfile />} />
            <Route path="knowledge-base" element={<KnowledgeBase />} />
            <Route path="resources" element={<ResourceGeneration />} />
            <Route path="report" element={<LearningReport />} />
            <Route path="guidance" element={<AdaptiveGuidance />} />
            <Route path="enterprise" element={<Navigate to="/dashboard" replace />} />
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
