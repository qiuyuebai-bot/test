import { http } from '../lib/request'
import type { LoginResponse } from '../types'

export interface DesktopBootstrapStatus {
  required: boolean
}

export const desktopApi = {
  status(): Promise<DesktopBootstrapStatus> {
    return http.get<DesktopBootstrapStatus>('/desktop/bootstrap-status', { silent: true, skipAuth: true })
  },
  bootstrap(data: { username: string; password: string }): Promise<LoginResponse> {
    return http.post<LoginResponse>('/desktop/bootstrap', data, { silent: true, skipAuth: true })
  },
}
