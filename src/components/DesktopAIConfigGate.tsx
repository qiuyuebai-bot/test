import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { aiConfigApi } from '../api'
import { useStore } from '../store'

/** 桌面端仅在首次登录且未配置 AI 时打开现有配置页。 */
export default function DesktopAIConfigGate() {
  const navigate = useNavigate()
  const location = useLocation()
  const userId = useStore((state) => state.user?.userId)
  const checkedUserId = useRef<number | undefined>()

  useEffect(() => {
    if (!window.zhiyuDesktop?.isDesktop || !userId || location.pathname === '/ai-config') return
    if (checkedUserId.current === userId) return
    checkedUserId.current = userId
    void aiConfigApi
      .get()
      .then((config) => {
        if (!config.configured && !config.apiKeyConfigured && !config.onboardingDismissed) {
          navigate('/ai-config?onboarding=1', { replace: true })
        }
      })
      .catch(() => {
        // 配置服务暂不可用时不阻塞用户进入已有的本地功能。
      })
  }, [location.pathname, navigate, userId])

  return null
}
