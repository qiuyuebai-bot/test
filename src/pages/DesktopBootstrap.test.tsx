import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { desktopApiMock, authApiMock, navigateMock, setTokensMock, setUserInfoMock, completedMock, storeMock } = vi.hoisted(() => {
  const useStore = vi.fn()
  Object.assign(useStore, { setState: vi.fn() })
  return {
    desktopApiMock: { bootstrap: vi.fn() },
    authApiMock: { getCurrentUser: vi.fn() },
    navigateMock: vi.fn(),
    setTokensMock: vi.fn(),
    setUserInfoMock: vi.fn(),
    completedMock: vi.fn(),
    storeMock: useStore,
  }
})

vi.mock('../api/desktop', () => ({ desktopApi: desktopApiMock }))
vi.mock('../api', () => ({ authApi: authApiMock }))
vi.mock('../lib/request', () => ({
  ApiError: class ApiError extends Error {},
  setTokens: setTokensMock,
  setUserInfo: setUserInfoMock,
}))
vi.mock('../store', () => ({ useStore: storeMock }))
vi.mock('react-router-dom', () => ({ useNavigate: () => navigateMock }))

import DesktopBootstrap from './DesktopBootstrap'

describe('DesktopBootstrap', () => {
  it('shows a focused validation error before contacting the desktop API', async () => {
    const user = userEvent.setup()
    render(<DesktopBootstrap />)

    await user.type(screen.getByLabelText('管理员用户名'), 'ab')
    await user.click(screen.getByRole('button', { name: '创建并进入工作台' }))

    expect(screen.getByRole('alert')).toHaveTextContent('用户名应为 3-50 位字母、数字或下划线')
    expect(desktopApiMock.bootstrap).not.toHaveBeenCalled()
  })

  it('creates the local administrator and enters the dashboard', async () => {
    const user = userEvent.setup()
    desktopApiMock.bootstrap.mockResolvedValue({
      userId: 42,
      username: 'local_admin',
      role: 'admin',
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
    })
    authApiMock.getCurrentUser.mockResolvedValue({ userId: 42, username: 'local_admin', role: 'admin' })
    render(<DesktopBootstrap onCompleted={completedMock} />)

    await user.type(screen.getByLabelText('管理员用户名'), 'local_admin')
    await user.type(screen.getByLabelText('密码'), 'LocalPass2026')
    await user.type(screen.getByLabelText('确认密码'), 'LocalPass2026')
    await user.click(screen.getByRole('button', { name: '创建并进入工作台' }))

    await waitFor(() => expect(desktopApiMock.bootstrap).toHaveBeenCalledWith({
      username: 'local_admin',
      password: 'LocalPass2026',
    }))
    expect(setTokensMock).toHaveBeenCalledWith('access-token', 'refresh-token')
    expect(setUserInfoMock).toHaveBeenCalledWith({ user_id: 42, username: 'local_admin', role: 'admin' })
    expect(completedMock).toHaveBeenCalledOnce()
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/dashboard', { replace: true }))
  })
})
