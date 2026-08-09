import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { ErrorBoundary } from './components'
import { QueryProvider } from './components/QueryProvider'
import { initSentry } from './lib/sentry'
import './index.css'

initSentry()

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryProvider>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </QueryProvider>
  </React.StrictMode>,
)
