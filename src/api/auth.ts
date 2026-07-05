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

  verifyToken(): Promise<{ userId: number; username: string; role: string; valid: boolean }> {
    return http.get('/auth/verify')
  },

  changePassword(data: { oldPassword: string; newPassword: string }): Promise<null> {
    return http.post<null>('/auth/change-password', data)
  },
}
