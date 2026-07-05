import { useState, useEffect, useCallback } from 'react'
import { privacyApi } from '@/api'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import LoadingState from '@/components/LoadingState'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import {
  Shield,
  Lock,
  Eye,
  EyeOff,
  Key,
  CheckCircle2,
  AlertCircle,
  FileText,
  Download,
  RefreshCw,
  UserCog,
  Settings,
  ClipboardList,
} from 'lucide-react'
import type {
  PrivacyComplianceItem,
  PrivacyAnonymizationRule,
  PrivacyPermissionItem,
  PrivacyKeyInfo,
  PrivacyDocument,
  PrivacyOverview,
} from '@/types'

export default function DataPrivacy() {
  const [showKeys, setShowKeys] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [overview, setOverview] = useState<PrivacyOverview | null>(null)
  const [compliance, setCompliance] = useState<PrivacyComplianceItem[]>([])
  const [anonymizationRules, setAnonymizationRules] = useState<PrivacyAnonymizationRule[]>([])
  const [permissions, setPermissions] = useState<PrivacyPermissionItem[]>([])
  const [keys, setKeys] = useState<PrivacyKeyInfo[]>([])
  const [documents, setDocuments] = useState<PrivacyDocument[]>([])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ov, comp, anon, perms, ks, docs] = await Promise.all([
        privacyApi.getOverview().catch(() => null),
        privacyApi.getCompliance().catch(() => [] as PrivacyComplianceItem[]),
        privacyApi.getAnonymization().catch(() => [] as PrivacyAnonymizationRule[]),
        privacyApi.getPermissions().catch(() => [] as PrivacyPermissionItem[]),
        privacyApi.getKeys().catch(() => [] as PrivacyKeyInfo[]),
        privacyApi.getDocuments().catch(() => [] as PrivacyDocument[]),
      ])
      if (ov) setOverview(ov as PrivacyOverview)
      setCompliance(comp as PrivacyComplianceItem[])
      setAnonymizationRules(anon as PrivacyAnonymizationRule[])
      setPermissions(perms as PrivacyPermissionItem[])
      setKeys(ks as PrivacyKeyInfo[])
      setDocuments(docs as PrivacyDocument[])
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载数据失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleTestAnonymization = async () => {
    if (anonymizationRules.length === 0) return
    setIsTesting(true)
    try {
      const fieldMap: Record<number, string> = {
        1: 'name',
        2: 'phone',
        3: 'idcard',
        4: 'email',
        5: 'address',
      }
      const updated = await Promise.all(
        anonymizationRules.map(async (rule) => {
          const fieldType = fieldMap[rule.id] || 'default'
          try {
            const result = await privacyApi.testAnonymization(fieldType, rule.original)
            return { ...rule, anonymized: result.anonymized, method: result.method }
          } catch {
            return rule
          }
        }),
      )
      setAnonymizationRules(updated)
    } finally {
      setIsTesting(false)
    }
  }

  if (loading) return <LoadingState type="default" />

  if (error) {
    return <ErrorState type="default" onRetry={() => loadData()} />
  }

  const pendingCount = overview?.pendingCount ?? compliance.filter((i) => i.status !== 'pass').length
  const ruleCount = overview?.anonymizationRuleCount ?? anonymizationRules.length
  const complianceStatus = overview?.complianceStatus ?? (pendingCount === 0 ? 'compliant' : 'warning')
  const encryptionStandard = overview?.encryptionStandard ?? 'AES-256'

  return (
    <div className="space-y-5 animate-fade-in">
      {/* 隐私合规状态总览 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-success/10 flex items-center justify-center">
              <Shield className="w-5 h-5 text-success" />
            </div>
            <div>
              <p className="text-xl font-semibold text-success">
                {complianceStatus === 'compliant' ? '合规' : '待改进'}
              </p>
              <p className="text-xs text-text-tertiary">合规状态</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
              <Lock className="w-5 h-5 text-primary" />
            </div>
            <div>
              <p className="text-xl font-semibold text-text-primary">{encryptionStandard}</p>
              <p className="text-xs text-text-tertiary">加密标准</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-info/10 flex items-center justify-center">
              <Key className="w-5 h-5 text-info" />
            </div>
            <div>
              <p className="text-xl font-semibold text-text-primary">{ruleCount}</p>
              <p className="text-xs text-text-tertiary">脱敏规则</p>
            </div>
          </div>
        </Card>
        <Card padding="md" className="hover:shadow-soft transition-all">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center">
              <AlertCircle className="w-5 h-5 text-amber-500" />
            </div>
            <div>
              <p className="text-xl font-semibold text-amber-500">{pendingCount}</p>
              <p className="text-xs text-text-tertiary">待处理项</p>
            </div>
          </div>
        </Card>
      </div>

      {/* 主内容区 */}
      <div className="grid grid-cols-12 gap-4">
        {/* 左侧：隐私合规检查 & 脱敏规则 */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          {/* 隐私合规检查 */}
          <Card padding="none">
            <div className="p-4 border-b border-border">
              <div className="flex items-center gap-2">
                <ClipboardList className="w-4 h-4 text-text-secondary" />
                <h3 className="text-sm font-semibold text-text-primary">隐私合规检查</h3>
                <Badge variant={complianceStatus === 'compliant' ? 'success' : 'warning'} size="sm">
                  {complianceStatus === 'compliant' ? 'GDPR 符合' : '待改进'}
                </Badge>
              </div>
            </div>
            {compliance.length === 0 ? (
              <div className="p-6">
                <EmptyState type="default" title="暂无合规检查数据" description="请稍后重试" />
              </div>
            ) : (
              <div className="divide-y divide-border/30">
                {compliance.map((item) => (
                  <div
                    key={item.id}
                    className="px-4 py-3 flex items-center justify-between hover:bg-bg-secondary/30 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      {item.status === 'pass' ? (
                        <CheckCircle2 className="w-5 h-5 text-success flex-shrink-0" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0" />
                      )}
                      <div>
                        <div className="flex items-center gap-2 mb-0.5">
                          <Badge variant="default" size="sm">{item.category}</Badge>
                          <span className="text-sm text-text-primary">{item.requirement}</span>
                        </div>
                        <p className="text-xs text-text-tertiary">
                          检查于 {item.lastCheck}
                          {item.detail && <span className="ml-2">· {item.detail}</span>}
                        </p>
                      </div>
                    </div>
                    <Badge variant={item.status === 'pass' ? 'success' : 'warning'} size="sm">
                      {item.status === 'pass' ? '通过' : '待改进'}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* 数据脱敏规则 */}
          <Card padding="none">
            <div className="p-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Settings className="w-4 h-4 text-text-secondary" />
                <h3 className="text-sm font-semibold text-text-primary">数据脱敏规则可视化</h3>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleTestAnonymization}
                loading={isTesting}
                disabled={anonymizationRules.length === 0}
              >
                <RefreshCw className="w-4 h-4" />
                测试脱敏
              </Button>
            </div>
            <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-3">
              {anonymizationRules.length === 0 ? (
                <div className="col-span-2">
                  <EmptyState type="data" title="暂无脱敏规则" description="请稍后重试或检查后端服务" />
                </div>
              ) : (
                anonymizationRules.map((rule) => (
                  <div
                    key={rule.id}
                    className="p-4 rounded-xl border border-border bg-bg-secondary/20 hover:border-primary/20 transition-all"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-text-primary">{rule.field}</span>
                        <Badge variant={rule.status === 'active' ? 'success' : 'default'} size="sm">
                          {rule.status === 'active' ? '已启用' : '草稿'}
                        </Badge>
                      </div>
                      <span className="text-xs text-text-tertiary">{rule.method}</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="p-2 rounded-lg bg-bg-card/50">
                        <p className="text-[10px] text-text-tertiary mb-0.5">原始数据</p>
                        <p className="text-xs text-text-secondary font-mono truncate">{rule.original}</p>
                      </div>
                      <div className="p-2 rounded-lg bg-success/5 border border-success/20">
                        <p className="text-[10px] text-success mb-0.5">脱敏后</p>
                        <p className="text-xs text-success font-mono truncate">{rule.anonymized}</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>

        {/* 右侧：密钥管理 & 权限管控 */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          {/* 密钥管理 */}
          <Card padding="md">
            <h4 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <Key className="w-4 h-4 text-text-secondary" />
              密钥管理
            </h4>
            {keys.length === 0 ? (
              <EmptyState type="default" title="暂无密钥信息" />
            ) : (
              keys.map((k) => (
                <div key={k.name} className="p-3 rounded-xl border border-border bg-bg-secondary/20">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
                        <Key className="w-4 h-4 text-amber-500" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-text-primary">{k.name}</p>
                        <p className="text-xs text-text-tertiary">{k.description}</p>
                      </div>
                    </div>
                    <Badge variant={k.isConfigured ? 'success' : 'warning'} size="sm">
                      {k.algorithm}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 px-2.5 py-1.5 rounded-lg bg-bg-card font-mono text-xs text-text-secondary truncate">
                      {showKeys ? k.maskedValue : '••••••••••••••••••••••••••'}
                    </div>
                    <button
                      onClick={() => setShowKeys(!showKeys)}
                      className="p-1.5 rounded-lg hover:bg-bg-secondary transition-colors"
                    >
                      {showKeys ? <EyeOff className="w-4 h-4 text-text-tertiary" /> : <Eye className="w-4 h-4 text-text-tertiary" />}
                    </button>
                  </div>
                  {!k.isConfigured && (
                    <p className="mt-2 text-xs text-amber-500">⚠ 密钥未配置，请设置环境变量 SECRET_KEY</p>
                  )}
                </div>
              ))
            )}
          </Card>

          {/* 数据权限管控 */}
          <Card padding="md">
            <h4 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <UserCog className="w-4 h-4 text-text-secondary" />
              数据权限管控
            </h4>
            <div className="space-y-2">
              {permissions.length === 0 ? (
                <EmptyState type="default" title="暂无权限配置" />
              ) : (
                permissions.map((perm) => (
                  <div key={perm.role} className="p-3 rounded-xl border border-border/50 bg-bg-secondary/20">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-text-primary">{perm.role}</span>
                      <Badge variant="default" size="sm">{perm.dataAccess}</Badge>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-text-tertiary">
                      <span className={`flex items-center gap-1 ${perm.exportAllowed ? 'text-success' : ''}`}>
                        {perm.exportAllowed ? <CheckCircle2 className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                        数据导出
                      </span>
                      <span className={`flex items-center gap-1 ${perm.deleteAllowed ? 'text-success' : ''}`}>
                        {perm.deleteAllowed ? <CheckCircle2 className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                        数据删除
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>

          {/* 合规文档 */}
          <Card padding="md">
            <h4 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4 text-text-secondary" />
              合规文档
            </h4>
            <div className="space-y-2">
              {documents.length === 0 ? (
                <EmptyState type="default" title="暂无文档" />
              ) : (
                documents.map((doc) => (
                  <button
                    key={doc.url}
                    className="w-full p-3 rounded-xl border border-border hover:border-primary/20 hover:bg-primary/5 transition-all flex items-center justify-between"
                    onClick={() => window.open(doc.url, '_blank')}
                  >
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-primary" />
                      <span className="text-sm text-text-primary">{doc.title}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-text-tertiary">{doc.date}</span>
                      <Download className="w-4 h-4 text-text-tertiary" />
                    </div>
                  </button>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* 隐私说明模块 */}
      <Card padding="md">
        <h3 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
          <Shield className="w-4 h-4 text-text-secondary" />
          隐私说明
        </h3>
        <div className="p-4 rounded-xl bg-primary/5 border border-primary/20">
          <p className="text-sm text-text-secondary leading-relaxed">
            本系统严格遵循《个人信息保护法》及《通用数据保护条例》（GDPR）要求。所有用户数据均经过加密存储处理，敏感信息按照脱敏规则自动处理，确保个人隐私安全。
            系统仅在用户授权范围内使用数据，且支持用户随时申请查看、导出或删除个人数据。
          </p>
        </div>
      </Card>
    </div>
  )
}
