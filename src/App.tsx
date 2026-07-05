import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense, useEffect } from 'react'
import Layout from './components/Layout'
import ToastContainer from './components/Toast'
import { PageSkeleton } from './components/Skeleton'
import { ProtectedRoute, PublicOnlyRoute } from './components/ProtectedRoute'
import { useStore } from './store'

const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const MultiAgentVisualization = lazy(() => import('./pages/MultiAgentVisualization'))
const LearnerProfile = lazy(() => import('./pages/LearnerProfile'))
const KnowledgeBase = lazy(() => import('./pages/KnowledgeBase'))
const ResourceGeneration = lazy(() => import('./pages/ResourceGeneration'))
const LearningReport = lazy(() => import('./pages/LearningReport'))
const AdaptiveGuidance = lazy(() => import('./pages/AdaptiveGuidance'))
const EnterpriseTraining = lazy(() => import('./pages/EnterpriseTraining'))
const DataPrivacy = lazy(() => import('./pages/DataPrivacy'))
const SystemTest = lazy(() => import('./pages/SystemTest'))
const Deployment = lazy(() => import('./pages/Deployment'))
const MetricsDashboard = lazy(() => import('./pages/MetricsDashboard'))

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
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="multi-agent" element={<MultiAgentVisualization />} />
            <Route path="profile" element={<LearnerProfile />} />
            <Route path="knowledge-base" element={<KnowledgeBase />} />
            <Route path="resources" element={<ResourceGeneration />} />
            <Route path="report" element={<LearningReport />} />
            <Route path="guidance" element={<AdaptiveGuidance />} />
            <Route path="enterprise" element={<EnterpriseTraining />} />
            <Route path="privacy" element={<DataPrivacy />} />
            <Route path="test" element={<SystemTest />} />
            <Route path="deployment" element={<Deployment />} />
            <Route path="metrics" element={<MetricsDashboard />} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
      <ToastContainer />
    </BrowserRouter>
  )
}

export default App
