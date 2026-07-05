import { ReactNode, isValidElement, ElementType } from 'react'
import { clsx } from 'clsx'
import Card from './Card'
import Button from './Button'
import { Inbox, Search, FileX, Users, Database, FileText, LucideIcon } from 'lucide-react'

interface EmptyStateProps {
  type?: 'default' | 'search' | 'file' | 'users' | 'data' | 'document'
  icon?: LucideIcon | ElementType | ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

const defaultIcons: Record<string, LucideIcon> = {
  default: Inbox,
  search: Search,
  file: FileX,
  users: Users,
  data: Database,
  document: FileText,
}

function isComponent(value: unknown): value is ElementType {
  if (typeof value === 'function') return true
  if (value !== null && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    return typeof obj.$$typeof === 'symbol'
  }
  return false
}

export default function EmptyState({
  type = 'default',
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  const IconComponent: ElementType = isComponent(icon) ? (icon as ElementType) : defaultIcons[type]

  return (
    <Card className={clsx('flex flex-col items-center justify-center py-12 px-6 text-center', className)}>
      <div className="w-16 h-16 rounded-2xl bg-bg-secondary flex items-center justify-center mb-5 transition-all duration-300">
        {icon && isValidElement(icon) ? icon : <IconComponent className="w-8 h-8 text-text-tertiary" />}
      </div>
      <h3 className="text-base font-medium text-text-primary mb-2">{title}</h3>
      {description && (
        <p className="text-sm text-text-secondary max-w-sm mb-5 leading-relaxed">{description}</p>
      )}
      {action}
    </Card>
  )
}

// 预设的空状态场景
EmptyState.Search = function SearchEmpty() {
  return (
    <EmptyState
      type="search"
      title="未找到搜索结果"
      description="尝试调整搜索条件或关键词"
    />
  )
}

EmptyState.Users = function UsersEmpty() {
  return (
    <EmptyState
      type="users"
      title="暂无学习者"
      description="添加学习者档案以开始个性化学习之旅"
      action={<Button variant="outline">添加学习者</Button>}
    />
  )
}

EmptyState.Data = function DataEmpty() {
  return (
    <EmptyState
      type="data"
      title="知识库为空"
      description="上传领域知识文档以构建专业内容库"
      action={<Button variant="outline">上传文档</Button>}
    />
  )
}

EmptyState.Document = function DocumentEmpty() {
  return (
    <EmptyState
      type="document"
      title="暂无资源"
      description="系统将根据学习者画像自动生成个性化资源"
    />
  )
}