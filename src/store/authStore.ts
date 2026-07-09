import type { StateCreator } from 'zustand'
import type { UserInfo } from '../types'
import { authApi } from '../api'
import { clearAuth, setTokens, setUserInfo, getUserInfo, isAuthenticated } from '../lib/request'
import { setSentryUser } from '../lib/sentry'
import type { AppState } from './index'

export interface AuthSlice {
  user: UserInfo | null
  isLoggedIn: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  fetchCurrentUser: () => Promise<void>
  initializeAuth: () => void
}

let _authListenerRegistered = false

export const createAuthSlice: StateCreator<AppState, [], [], AuthSlice> = (set, get) => ({
  user: (typeof window !== 'undefined' && isAuthenticated() ? getUserInfo() : null) as UserInfo | null,
  isLoggedIn: typeof window !== 'undefined' && isAuthenticated(),
  isLoading: false,

  login: async (username: string, password: string) => {
    set({ isLoading: true })
    try {
      const result = await authApi.login({ username, password })
      setTokens(result.accessToken, result.refreshToken)
      setUserInfo({ user_id: result.userId, username: result.username, role: result.role })
      setSentryUser({ id: String(result.userId), username: result.username, role: result.role })
      const userInfo = await authApi.getCurrentUser()
      set({ user: userInfo, isLoggedIn: true, isLoading: false })
    } catch (error) {
      set({ isLoading: false })
      throw error
    }
  },

  logout: async () => {
    try {
      await authApi.logout()
    } catch (err) {
      console.error('logout failed:', err)
    }
    clearAuth()
    setSentryUser(null)
    set({ user: null, isLoggedIn: false, currentLearner: null, currentTask: null })
  },

  fetchCurrentUser: async () => {
    if (!isAuthenticated()) return
    try {
      const userInfo = await authApi.getCurrentUser()
      set({ user: userInfo, isLoggedIn: true })
    } catch (err) {
      console.error('fetchCurrentUser failed:', err)
      clearAuth()
      set({ user: null, isLoggedIn: false })
    }
  },

  initializeAuth: () => {
    const savedUser = getUserInfo()
    if (savedUser && isAuthenticated()) {
      set({ isLoggedIn: true, user: savedUser as UserInfo })
      get().fetchCurrentUser()
    }
    if (typeof window !== 'undefined' && !_authListenerRegistered) {
      _authListenerRegistered = true
      window.addEventListener('auth:logout', () => {
        set({ user: null, isLoggedIn: false })
      })
    }
  },
})
