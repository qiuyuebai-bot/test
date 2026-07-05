import { Navigate, useLocation } from 'react-router-dom'
import { useStore } from '../store'
import type { UserRole } from '../types'

interface ProtectedRouteProps {
  children: React.ReactNode
  roles?: UserRole[]
}

export function ProtectedRoute({ children, roles }: ProtectedRouteProps) {
  const isLoggedIn = useStore((s) => s.isLoggedIn)
  const user = useStore((s) => s.user)
  const location = useLocation()

  if (!isLoggedIn || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (roles && roles.length > 0 && !roles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

export function PublicOnlyRoute({ children }: ProtectedRouteProps) {
  const isLoggedIn = useStore((s) => s.isLoggedIn)
  const location = useLocation()
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/'

  if (isLoggedIn) {
    return <Navigate to={from} replace />
  }

  return <>{children}</>
}

interface RoleGuardProps {
  children: React.ReactNode
  roles: UserRole[]
  fallback?: React.ReactNode
}

export function RoleGuard({ children, roles, fallback = null }: RoleGuardProps) {
  const user = useStore((s) => s.user)

  if (!user || !roles.includes(user.role)) {
    return <>{fallback}</>
  }

  return <>{children}</>
}
