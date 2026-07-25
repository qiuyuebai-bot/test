import { http } from '../lib/request'
import type { UserInfo, LoginRequest, LoginResponse } from '../types'

export const authApi = {
  login(data: LoginRequest): Promise<LoginResponse> {
    return http.post<LoginResponse>('/auth/login', data)
  },

  register(data: { username: string; password: string; email?: string; role?: string }): Promise<LoginResponse> {
    return http.post<LoginResponse>('/auth/register', data)
  },

  logout(): Promise<null> {
    return http.post<null>('/auth/logout')
  },

  getCurrentUser(): Promise<UserInfo> {
    return http.get<UserInfo>('/auth/me')
  },

  setOnboardingName(data: { name: string }): Promise<{ id: number; realName: string }> {
    return http.post<{ id: number; realName: string }>('/auth/onboarding/name', data)
  },

  verifyToken(): Promise<{ userId: number; username: string; role: string; valid: boolean }> {
    return http.get('/auth/verify')
  },

  changePassword(data: { oldPassword: string; newPassword: string }): Promise<null> {
    return http.post<null>('/auth/change-password', data)
  },
}
