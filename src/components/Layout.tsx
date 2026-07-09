import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useStore } from '@/store'
import PageTransition from './PageTransition'
import {
  LayoutDashboard,
  Network,
  UserCircle,
  Database,
  FileText,
  BarChart3,
  GraduationCap,
  Building2,
  Shield,
  FlaskConical,
  Rocket,
  TrendingUp,
  Menu,
  Moon,
  Sun,
  X,
  LogOut,
  ChevronDown,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useState, useEffect, useRef } from 'react'

const navigation = [
  { name: '数据看板', href: '/dashboard', icon: LayoutDashboard },
  { name: '多智能体协同', href: '/multi-agent', icon: Network },
  { name: '学习者画像', href: '/profile', icon: UserCircle },
  { name: '领域知识库', href: '/knowledge-base', icon: Database },
  { name: '资源生成', href: '/resources', icon: FileText },
  { name: '学情报告', href: '/report', icon: BarChart3 },
  { name: '自适应导学', href: '/guidance', icon: GraduationCap },
  { name: '量化指标', href: '/metrics', icon: TrendingUp },
]

const secondaryNav = [
  { name: '企业内训', href: '/enterprise', icon: Building2 },
  { name: '隐私合规', href: '/privacy', icon: Shield },
  { name: '系统测试', href: '/test', icon: FlaskConical },
  { name: '部署说明', href: '/deployment', icon: Rocket },
]

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const isSidebarCollapsed = useStore((s) => s.isSidebarCollapsed)
  const toggleSidebar = useStore((s) => s.toggleSidebar)
  const isDarkMode = useStore((s) => s.isDarkMode)
  const toggleDarkMode = useStore((s) => s.toggleDarkMode)
  const user = useStore((s) => s.user)
  const logout = useStore((s) => s.logout)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMobileMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  const roleMap: Record<string, string> = {
    admin: '管理员',
    teacher: '教师',
    learner: '学习者',
  }

  const sidebarContent = (
    <>
      {/* Logo 区域 */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center flex-shrink-0">
            <Network className="w-4 h-4 text-white" />
          </div>
          {!isSidebarCollapsed && (
            <span className="font-semibold text-text-primary tracking-tight whitespace-nowrap">
              多智能体系统
            </span>
          )}
        </div>
        {/* 移动端关闭按钮 */}
        <button
          onClick={() => setMobileMenuOpen(false)}
          className="lg:hidden p-1.5 rounded-lg text-text-tertiary hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* 主导航 */}
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
        {navigation.map((item) => {
          const isActive = location.pathname === item.href
          return (
            <Link
              key={item.name}
              to={item.href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
                isActive
                  ? 'bg-primary-light text-primary font-medium'
                  : 'text-text-secondary hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-text-primary'
              )}
            >
              <item.icon className={clsx('w-5 h-5 flex-shrink-0', isActive && 'text-primary')} />
              {!isSidebarCollapsed && <span className="text-sm whitespace-nowrap">{item.name}</span>}
            </Link>
          )
        })}

        <div className="pt-4 mt-4 border-t border-border">
          {secondaryNav.map((item) => {
            const isActive = location.pathname === item.href
            return (
              <Link
                key={item.name}
                to={item.href}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200',
                  isActive
                    ? 'bg-primary-light text-primary font-medium'
                    : 'text-text-secondary hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-text-primary'
                  )}
              >
                <item.icon className={clsx('w-5 h-5 flex-shrink-0', isActive && 'text-primary')} />
                {!isSidebarCollapsed && <span className="text-sm whitespace-nowrap">{item.name}</span>}
              </Link>
            )
          })}
        </div>
      </nav>

      {/* 底部折叠按钮 */}
      <div className="p-3 border-t border-border hidden lg:block">
        <button
          onClick={toggleSidebar}
          aria-expanded={!isSidebarCollapsed}
          aria-label="切换侧边栏"
          className="flex items-center justify-center w-full py-2 rounded-lg text-text-tertiary hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
      </div>
    </>
  )

  return (
    <div className="flex h-screen bg-bg-secondary overflow-hidden">
      {/* 移动端遮罩 */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* 桌面端侧边栏 */}
      <aside
        className={clsx(
          'hidden lg:flex flex-col bg-bg-card border-r border-border transition-all duration-300',
          isSidebarCollapsed ? 'w-[72px]' : 'w-[260px]'
        )}
      >
        {sidebarContent}
      </aside>

      {/* 移动端侧边栏 */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 flex flex-col bg-bg-card border-r border-border transition-transform duration-300 w-[260px] lg:hidden',
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {sidebarContent}
      </aside>

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* 顶部栏 */}
        <header className="h-16 bg-bg-card border-b border-border flex items-center justify-between px-4 md:px-6 flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {/* 移动端菜单按钮 */}
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-1.5 rounded-lg text-text-secondary hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors flex-shrink-0"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h1 className="text-base md:text-lg font-medium text-text-primary truncate">
              {navigation.find((n) => n.href === location.pathname)?.name ||
               secondaryNav.find((n) => n.href === location.pathname)?.name ||
               '领域知识个性化生成与多智能体协同决策系统'}
            </h1>
          </div>
          <div className="flex items-center gap-2 md:gap-3 flex-shrink-0">
            <button
              onClick={toggleDarkMode}
              className="p-2 rounded-lg text-text-secondary hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              title={isDarkMode ? '切换到浅色模式' : '切换到深色模式'}
            >
              {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
            <div className="relative" ref={userMenuRef}>
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                aria-expanded={userMenuOpen}
                aria-haspopup="true"
                className="flex items-center gap-2 p-1.5 pr-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                  <span className="text-sm text-white font-medium">
                    {user?.username?.charAt(0)?.toUpperCase() || 'U'}
                  </span>
                </div>
                <div className="hidden md:block text-left">
                  <p className="text-sm font-medium text-text-primary leading-tight">
                    {user?.username || '用户'}
                  </p>
                  <p className="text-xs text-text-tertiary leading-tight">
                    {roleMap[user?.role || ''] || user?.role || ''}
                  </p>
                </div>
                <ChevronDown className={clsx('w-4 h-4 text-text-tertiary transition-transform hidden md:block', userMenuOpen && 'rotate-180')} />
              </button>
              {userMenuOpen && (
                <div className="absolute right-0 top-full mt-2 w-48 bg-bg-card rounded-xl border border-border shadow-lg py-1 z-50">
                  <div className="px-4 py-2 border-b border-border">
                    <p className="text-sm font-medium text-text-primary">{user?.username}</p>
                    <p className="text-xs text-text-tertiary">{roleMap[user?.role || ''] || user?.role}</p>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                  >
                    <LogOut className="w-4 h-4" />
                    退出登录
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* 内容区域 */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6 bg-bg-secondary">
          <PageTransition>
            <Outlet />
          </PageTransition>
        </main>
      </div>
    </div>
  )
}