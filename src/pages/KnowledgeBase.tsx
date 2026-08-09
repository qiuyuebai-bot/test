import { useState, useEffect, useRef } from 'react'
import { useStore } from '@/store'
import { useShallow } from 'zustand/react/shallow'
import type { KnowledgeDoc, KnowledgeSearchResult } from '@/types'
import { configApi, knowledgeApi } from '@/api'
import type { DomainOption } from '@/api/config'
import Card from '@/components/Card'
import Modal from '@/components/Modal'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import {
  Database,
  Upload,
  Search,
  FileText,
  Layers,
  CheckCircle,
  Clock,
  AlertCircle,
  Trash2,
  Download,
  Eye,
  Link,
  BookOpen,
  FileSearch,
  AlertTriangle,
  RefreshCw,
} from 'lucide-react'
import EmptyState from '@/components/EmptyState'
import ErrorState from '@/components/ErrorState'
import { PageSkeleton } from '@/components/Skeleton'
import { toast } from '@/components/toastStore'

const statusConfig = {
  indexed: { label: '已索引', color: 'bg-success/10 text-success border-success/20', icon: CheckCircle },
  pending: { label: '处理中', color: 'bg-warning-light text-warning-dark border-warning/30', icon: Clock },
  error: { label: '异常', color: 'bg-error-light text-error-dark border-error/30', icon: AlertCircle },
}

function DomainTag({ domain, options }: { domain: string; options: DomainOption[] }) {
  const config = options.find(d => d.value === domain)
  const label = config?.label || domain
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-medium border transition-all hover:shadow-lift ${config?.color || 'bg-bg-secondary/30 text-text-secondary border-border'}`}>
      {label}
    </span>
  )
}

function DocPreviewModal({
  isOpen,
  onClose,
  doc,
  slices,
  slicesLoading,
  domainToLabel,
}: {
  isOpen: boolean
  onClose: () => void
  doc?: KnowledgeDoc
  slices: { id: number; sliceIndex: number; content: string; title?: string }[]
  slicesLoading: boolean
  domainToLabel: Record<string, string>
}) {
  if (!isOpen || !doc) return null

  return (
    <Modal isOpen={isOpen} onClose={onClose} maxWidth="max-w-2xl">
      <div className="p-5 border-b border-border flex items-center justify-between bg-bg-secondary/30">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <FileText className="w-5 h-5 text-primary" />
          </div>
          <div>
            <h3 className="font-semibold text-text-primary">{doc.title}</h3>
            <p className="text-sm text-text-tertiary">{domainToLabel[doc.domain] || doc.domain} · {doc.category}</p>
          </div>
        </div>
      </div>

        <div className="p-5 max-h-[400px] overflow-y-auto">
          {slicesLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin w-6 h-6 border-2 border-primary border-t-transparent rounded-full" />
            </div>
          ) : (
            <div className="space-y-4">
              {slices.map((slice) => (
                <div key={slice.id} className="p-4 rounded-xl bg-bg-secondary/50 border border-border/50 backdrop-blur-sm">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-text-secondary flex items-center gap-1">
                      <BookOpen className="w-3 h-3" />
                      {slice.title || `第 ${slice.sliceIndex + 1} 节`}
                    </span>
                    <Badge variant="default" size="sm">切片 #{slice.sliceIndex + 1}</Badge>
                  </div>
                  <p className="text-sm text-text-primary leading-relaxed">{slice.content}</p>
                </div>
              ))}
              {slices.length === 0 && (
                <div className="p-4 rounded-xl bg-bg-secondary/50 border border-border/50">
                  <p className="text-sm text-text-secondary text-center">文档切片正在索引中...</p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="p-5 border-t border-border bg-bg-secondary/30">
          <div className="flex items-center justify-between text-xs text-text-tertiary">
            <span className="flex items-center gap-1">
              <FileSearch className="w-3 h-3" />
              来源：{doc.source || '未知'}
            </span>
            <span className="flex items-center gap-1">
              <Layers className="w-3 h-3" />
              {doc.indexedSlices}/{doc.totalSlices} 个知识切片
            </span>
          </div>
        </div>
    </Modal>
  )
}

function TraceabilityModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [resourceId, setResourceId] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ slices?: Array<{ docTitle?: string; docId?: number; sliceIndex?: number; content?: string; similarity?: number }>; resourceTitle?: string; message?: string } | null>(null)
  const [error, setError] = useState('')

  useEffect(() => { if (!isOpen) { setResult(null); setError(''); setResourceId('') } }, [isOpen])

  const handleTrace = async () => {
    const id = parseInt(resourceId)
    if (!id) return
    setLoading(true)
    setError('')
    try {
      const res = await knowledgeApi.traceResource(id) as { data?: typeof result }
      const data = res?.data || res
      setResult(data as typeof result)
    } catch {
      setError('溯源查询失败，请确认资源 ID 有效')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <Modal isOpen={isOpen} onClose={onClose} maxWidth="max-w-3xl" className="p-8">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Link className="w-5 h-5 text-primary" />
          <h3 className="font-semibold text-text-primary">知识溯源关系图谱</h3>
        </div>
      </div>
      <p className="text-sm text-text-secondary mb-4">输入已生成资源的 ID，查询其引用了哪些知识库文档切片</p>
      <div className="flex items-center gap-3 mb-4">
        <input type="number" value={resourceId} onChange={e => setResourceId(e.target.value)} placeholder="输入资源 ID" className="w-40 h-10 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20" />
        <Button variant="primary" onClick={handleTrace} disabled={loading}>{loading ? '查询中…' : '开始溯源'}</Button>
      </div>
      {error && <p className="text-sm text-error mb-3">{error}</p>}
      {result ? (
        <div className="space-y-3">
          {result.resourceTitle && <p className="text-sm font-medium text-text-primary">资源：{result.resourceTitle}</p>}
          {(result.slices || []).length > 0 ? (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {(result.slices || []).map((slice, i) => (
                <div key={i} className="p-3 bg-bg-secondary rounded-lg border border-border text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="success" size="sm">文档 #{slice.docId}</Badge>
                    <span className="text-text-primary font-medium">{slice.docTitle || '未知文档'}</span>
                    <span className="text-text-tertiary">切片 {slice.sliceIndex}</span>
                  </div>
                  <p className="text-text-secondary text-xs line-clamp-2">{(slice.content || '').slice(0, 200)}</p>
                </div>
              ))}
            </div>
          ) : <EmptyState title="未找到关联切片" description="该资源可能没有关联的知识库切片" />}
          {result.message && <p className="text-xs text-text-tertiary">{result.message}</p>}
        </div>
      ) : <EmptyState title="请输入资源 ID" description="溯源结果将展示在此处" />}
      <div className="flex justify-end gap-3 mt-6">
        <Button variant="outline" onClick={onClose}>关闭</Button>
      </div>
    </Modal>
  )
}

function UploadModal({ isOpen, onClose, onSuccess }: { isOpen: boolean; onClose: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState({ title: '', industry: '人工智能训练', category: '', source: '', author: '', content: '' })
  const [uploading, setUploading] = useState(false)

  const industryOptions = ['智能制造', '工业互联网', '软件开发', '人工智能训练', '数据分析', '通用']

  useEffect(() => { if (!isOpen) setForm({ title: '', industry: '人工智能训练', category: '', source: '', author: '', content: '' }) }, [isOpen])

  const handleUpload = async () => {
    if (!form.title.trim() || !form.content.trim()) { toast.error('标题和内容不能为空'); return }
    setUploading(true)
    try {
      await knowledgeApi.uploadText({ title: form.title.trim(), industry: form.industry, content: form.content.trim(), category: form.category.trim() || undefined, source: form.source.trim() || undefined, author: form.author.trim() || undefined })
      toast.success('文档上传成功')
      onSuccess()
      onClose()
    } catch {
      toast.error('上传失败，请重试')
    } finally {
      setUploading(false)
    }
  }

  if (!isOpen) return null

  return (
    <Modal isOpen={isOpen} onClose={onClose} maxWidth="max-w-lg" className="p-8">
      <div className="flex items-center justify-between mb-5">
        <h3 className="text-lg font-semibold text-text-primary flex items-center gap-2"><Upload className="w-5 h-5 text-text-secondary" />导入知识文档</h3>
      </div>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">文档标题 *</label>
            <input type="text" value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20" placeholder="例如：反向传播算法详解" />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">所属行业</label>
            <select value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })} className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20">
              {industryOptions.map(name => <option key={name} value={name}>{name}</option>)}
            </select>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">分类</label>
            <input type="text" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20" placeholder="例如：深度学习" />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">来源</label>
            <input type="text" value={form.source} onChange={e => setForm({ ...form, source: e.target.value })} className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20" placeholder="例如：教材/论文" />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-primary mb-1.5">作者</label>
            <input type="text" value={form.author} onChange={e => setForm({ ...form, author: e.target.value })} className="w-full h-10 px-3 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20" placeholder="来源作者" />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-text-primary mb-1.5">文档内容 *</label>
          <textarea value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} rows={10} className="w-full px-3 py-2 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none" placeholder="粘贴或输入文档正文内容（至少 10 个字符）…" />
        </div>
      </div>
      <div className="flex justify-end gap-3 mt-6">
        <Button variant="outline" onClick={onClose}>取消</Button>
        <Button variant="primary" onClick={handleUpload} disabled={uploading}>{uploading ? '上传中…' : '上传文档'}</Button>
      </div>
    </Modal>
  )
}

export default function KnowledgeBase() {
  const { knowledgeDocs, knowledgeSlices, knowledgeLoading, knowledgeError, totalKnowledgeDocs } = useStore(
    useShallow((s) => ({
      knowledgeDocs: s.knowledgeDocs,
      knowledgeSlices: s.knowledgeSlices,
      knowledgeLoading: s.knowledgeLoading,
      knowledgeError: s.knowledgeError,
      totalKnowledgeDocs: s.totalKnowledgeDocs,
    }))
  )
  const { fetchKnowledgeDocs, fetchKnowledgeSlices } = useStore(
    useShallow((s) => ({
      fetchKnowledgeDocs: s.fetchKnowledgeDocs,
      fetchKnowledgeSlices: s.fetchKnowledgeSlices,
    }))
  )
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDomain, setSelectedDomain] = useState('all')
  const [showUpload, setShowUpload] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [showTraceability, setShowTraceability] = useState(false)
  const [selectedDoc, setSelectedDoc] = useState<KnowledgeDoc>()
  const [slicesLoading, setSlicesLoading] = useState(false)
  const [domainOptions, setDomainOptions] = useState<DomainOption[]>([])
  const [sliceSearchQuery, setSliceSearchQuery] = useState('')
  const [sliceSearchResults, setSliceSearchResults] = useState<KnowledgeSearchResult[]>([])
  const [sliceSearchLoading, setSliceSearchLoading] = useState(false)
  const [sliceSearchError, setSliceSearchError] = useState('')
  const [reindexingId, setReindexingId] = useState<number | null>(null)

  const previewReqIdRef = useRef(0)

  useEffect(() => {
    fetchKnowledgeDocs({ page: 1, pageSize: 50 })
  }, [fetchKnowledgeDocs])

  useEffect(() => {
    configApi.getOptions().then(opts => setDomainOptions(opts.domains)).catch(() => {})
  }, [])

  const domainToLabel: Record<string, string> = Object.fromEntries(
    domainOptions.map(d => [d.value, d.label])
  )

  const handleSliceSearch = async () => {
    const query = sliceSearchQuery.trim()
    if (!query) {
      setSliceSearchResults([])
      setSliceSearchError('')
      return
    }
    setSliceSearchLoading(true)
    setSliceSearchError('')
    try {
      const response = await knowledgeApi.search({ query, topK: 5, searchType: 'hybrid' })
      setSliceSearchResults(response.results || [])
    } catch (error) {
      setSliceSearchResults([])
      setSliceSearchError(error instanceof Error ? error.message : '检索失败，请稍后重试')
    } finally {
      setSliceSearchLoading(false)
    }
  }

  const filteredDocs = knowledgeDocs.filter((doc) => {
    const matchesSearch = doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          doc.category.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesDomain = selectedDomain === 'all' || doc.domain === selectedDomain
    return matchesSearch && matchesDomain
  })

  const stats = {
    total: knowledgeDocs.length,
    indexed: knowledgeDocs.filter(d => d.status === 'indexed').length,
    pending: knowledgeDocs.filter(d => d.status === 'pending').length,
    error: knowledgeDocs.filter(d => d.status === 'error').length,
    totalSlices: knowledgeDocs.reduce((sum, d) => sum + d.totalSlices, 0),
    indexedSlices: knowledgeDocs.reduce((sum, d) => sum + d.indexedSlices, 0),
  }

  const handlePreview = async (doc: KnowledgeDoc) => {
    const reqId = ++previewReqIdRef.current
    setSelectedDoc(doc)
    setShowPreview(true)
    setSlicesLoading(true)
    await fetchKnowledgeSlices(doc.id)
    if (reqId !== previewReqIdRef.current) return
    setSlicesLoading(false)
  }

  const handleImportSamples = async () => {
    const samples = [
      { title: '反向传播算法基础', industry: '人工智能训练', category: '深度学习', content: '反向传播（Backpropagation）是训练人工神经网络的核心算法。它通过链式法则计算损失函数相对于每个参数的梯度，然后使用梯度下降法更新参数。\n\n核心步骤：\n1. 前向传播：输入数据通过网络，计算每一层的输出和最终预测值\n2. 计算损失：使用损失函数比较预测值与真实标签\n3. 反向传播：从输出层向输入层逐层计算梯度\n4. 参数更新：根据梯度和学习率调整权重和偏置\n\n学习率是重要的超参数：过大导致震荡不收敛，过小收敛缓慢。常用优化器包括 SGD、Adam、RMSProp 等。' },
      { title: 'RESTful API 设计规范', industry: '软件开发', category: '后端开发', content: 'REST（Representational State Transfer）是一组软件架构原则，用于设计网络服务。\n\n核心原则：\n1. 资源导向：每个 URL 代表一个资源，名词复数形式\n2. HTTP 方法语义：GET 查询、POST 创建、PUT 全量更新、PATCH 部分更新、DELETE 删除\n3. 无状态：每个请求包含所有必要信息，服务端不保存客户端会话\n4. 统一接口：一致的响应格式和错误处理\n\n最佳实践：\n- 使用 JSON 作为数据格式\n- API 版本化（/api/v1/）\n- 适当的 HTTP 状态码（200/201/400/404/500）\n- 分页、过滤、排序支持\n- 认证使用 Bearer Token 或 OAuth 2.0\n- 限流防止滥用' },
      { title: '数据预处理与特征工程', industry: '数据分析', category: '数据科学', content: '数据预处理是机器学习和数据分析的关键步骤，直接影响模型质量。\n\n主要步骤：\n1. 数据清洗：处理缺失值（删除/均值填充/预测填充）、识别和处理异常值\n2. 数据集成：合并多个数据源，解决数据冗余和不一致\n3. 数据变换：标准化（Z-score）、归一化（MinMax）、对数变换\n4. 数据归约：特征选择、主成分分析、降维\n\n特征工程：\n- 数值特征：分箱、多项式特征、交叉特征\n- 类别特征：One-hot 编码、Label 编码、Embedding\n- 文本特征：TF-IDF、Word2Vec、BERT 嵌入\n- 时间特征：提取年月日、星期、节假日标记\n\n常用工具：Python pandas、scikit-learn、NumPy' },
    ]
    let success = 0
    for (const sample of samples) {
      try {
        await knowledgeApi.uploadText(sample)
        success++
      } catch { /* 跳过重复 */ }
    }
    await fetchKnowledgeDocs({ page: 1, pageSize: 50 })
    toast.success(`已导入 ${success}/${samples.length} 份样例文档`)
  }

  const handleUpload = () => {
    setShowUpload(true)
  }

  const [deleteTarget, setDeleteTarget] = useState<KnowledgeDoc | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const handleDownload = async (doc: KnowledgeDoc) => {
    try {
      const res = await knowledgeApi.getPreview(doc.id) as { slices?: Array<{ content: string; title?: string }> }
      const slices = res?.slices || []
      const text = slices.map((s, i) => `## 切片 ${i + 1}${s.title ? ` - ${s.title}` : ''}\n\n${s.content}`).join('\n\n---\n\n')
      const blob = new Blob([text || '暂无内容'], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${doc.title}.txt`
      a.click()
      URL.revokeObjectURL(url)
      toast.success('文档已下载')
    } catch {
      toast.error('下载失败')
    }
  }

  const handleDeleteClick = (doc: KnowledgeDoc) => {
    setDeleteTarget(doc)
    setShowDeleteConfirm(true)
  }

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await knowledgeApi.delete(deleteTarget.id)
      setShowDeleteConfirm(false)
      setDeleteTarget(null)
      await fetchKnowledgeDocs({ page: 1, pageSize: 50 })
      toast.success('文档已删除')
    } catch {
      toast.error('删除失败')
    } finally {
      setDeleting(false)
    }
  }

  const handleReindex = async (doc: KnowledgeDoc) => {
    setReindexingId(doc.id)
    try {
      const result = await knowledgeApi.reindex(doc.id)
      await fetchKnowledgeDocs({ page: 1, pageSize: 50 })
      toast.success(`已完成索引：${result.indexedSliceCount}/${result.sliceCount} 个切片`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '重新索引失败')
    } finally {
      setReindexingId(null)
    }
  }

  if (knowledgeLoading && knowledgeDocs.length === 0) return <PageSkeleton type="table" />
  if (knowledgeError) return <ErrorState type="default" onRetry={() => fetchKnowledgeDocs({ page: 1, pageSize: 50 })} />

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="hero-anchor text-xl font-semibold text-text-primary">垂直领域知识库管理</h1>
          <p className="text-sm text-text-secondary mt-1">支持多行业专业知识库导入、切片管理、内容检索</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => setShowTraceability(true)}>
            <Link className="w-4 h-4" />
            知识溯源
          </Button>
          <Button variant="outline" onClick={handleImportSamples}>
            <Download className="w-4 h-4" />
            导入样例
          </Button>
          <Button variant="primary" onClick={handleUpload}>
            <Upload className="w-4 h-4" />
            上传文档
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card padding="md" className="flex items-center gap-3 hover:shadow-lift transition-all">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
            <Database className="w-5 h-5 text-primary" />
          </div>
          <div>
            <p className="metric-number text-xl font-semibold text-text-primary">{stats.total}</p>
            <p className="text-xs text-text-secondary">文档总数</p>
          </div>
        </Card>
        <Card padding="md" className="flex items-center gap-3 hover:shadow-lift transition-all">
          <div className="w-10 h-10 rounded-xl bg-success/10 flex items-center justify-center">
            <CheckCircle className="w-5 h-5 text-success" />
          </div>
          <div>
            <p className="metric-number text-xl font-semibold text-text-primary">{stats.indexed}</p>
            <p className="text-xs text-text-secondary">已索引</p>
          </div>
        </Card>
        <Card padding="md" className="flex items-center gap-3 hover:shadow-lift transition-all">
          <div className="w-10 h-10 rounded-xl bg-warning-light flex items-center justify-center">
            <Clock className="w-5 h-5 text-warning" />
          </div>
          <div>
            <p className="metric-number text-xl font-semibold text-text-primary">{stats.pending}</p>
            <p className="text-xs text-text-secondary">处理中</p>
          </div>
        </Card>
        <Card padding="md" className="flex items-center gap-3 hover:shadow-lift transition-all">
          <div className="w-10 h-10 rounded-xl bg-info/10 flex items-center justify-center">
            <Layers className="w-5 h-5 text-info" />
          </div>
          <div>
            <p className="metric-number text-xl font-semibold text-text-primary">{stats.totalSlices}</p>
            <p className="text-xs text-text-secondary">知识切片</p>
          </div>
        </Card>
      </div>

      <Card padding="md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1 md:w-[280px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
              <input
                type="text"
                placeholder="搜索文档..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full h-10 pl-10 pr-4 bg-bg-secondary border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-tertiary">领域筛选：</span>
              <div className="flex gap-1">
                <button
                  onClick={() => setSelectedDomain('all')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${selectedDomain === 'all' ? 'bg-primary/10 text-primary border-primary/30' : 'bg-bg-secondary text-text-secondary border-border hover:border-primary/20'}`}
                >
                  全部
                </button>
                {domainOptions.map((d) => (
                  <button
                    key={d.value}
                    onClick={() => setSelectedDomain(d.value)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${selectedDomain === d.value ? d.color + ' border-current' : 'bg-bg-secondary text-text-secondary border-border hover:border-primary/20'}`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <span className="text-sm text-text-secondary">
            共 <span className="font-semibold text-primary">{filteredDocs.length}</span> 个文档
            {totalKnowledgeDocs > 0 && <span className="text-text-tertiary ml-1">(总计 {totalKnowledgeDocs})</span>}
          </span>
        </div>
      </Card>

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-8">
          <Card padding="none">
            {filteredDocs.length === 0 && !knowledgeLoading ? (
              <EmptyState
                icon={Database}
                title="暂无知识库文档"
                description="请上传文档或等待文档索引完成"
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border/50">
                      <th className="px-5 py-3 text-left text-xs font-medium text-text-secondary">文档信息</th>
                      <th className="px-5 py-3 text-left text-xs font-medium text-text-secondary">领域</th>
                      <th className="px-5 py-3 text-left text-xs font-medium text-text-secondary">切片数</th>
                      <th className="px-5 py-3 text-left text-xs font-medium text-text-secondary">状态</th>
                      <th className="px-5 py-3 text-right text-xs font-medium text-text-secondary">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredDocs.map((doc, index) => {
                      const status = statusConfig[doc.status as keyof typeof statusConfig] || statusConfig.pending
                      const StatusIcon = status.icon
                      return (
                        <tr
                          key={doc.id}
                          className={`border-b border-border/30 transition-colors hover:bg-bg-secondary/30 ${index % 2 === 1 ? 'bg-bg-secondary/20' : ''}`}
                        >
                          <td className="px-5 py-3">
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center transition-transform hover:scale-105">
                                <FileText className="w-4 h-4 text-primary" />
                              </div>
                              <div>
                                <p className="font-medium text-text-primary text-sm">{doc.title}</p>
                                <p className="text-xs text-text-tertiary">{doc.category}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-5 py-3">
                            <DomainTag domain={doc.domain} options={domainOptions} />
                          </td>
                          <td className="px-5 py-3">
                            <span className="text-sm font-medium text-text-primary">{doc.indexedSlices}/{doc.totalSlices}</span>
                            <span className="text-xs text-text-tertiary ml-1">切片</span>
                          </td>
                          <td className="px-5 py-3">
                            <span title={doc.errorMessage || undefined} className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium border ${status.color}`}>
                              <StatusIcon className="w-3 h-3" />
                              {status.label}
                            </span>
                          </td>
                          <td className="px-5 py-3">
                            <div className="flex items-center justify-end gap-1">
                              {(doc.status === 'error' || doc.status === 'pending') && (
                                <button
                                  onClick={() => void handleReindex(doc)}
                                  disabled={reindexingId === doc.id}
                                  className="p-2 rounded-lg hover:bg-bg-secondary transition-colors disabled:opacity-50"
                                  title="重新索引"
                                >
                                  <RefreshCw className={`w-4 h-4 text-text-tertiary ${reindexingId === doc.id ? 'animate-spin' : ''}`} />
                                </button>
                              )}
                              <button
                                onClick={() => handlePreview(doc)}
                                className="p-2 rounded-lg hover:bg-bg-secondary transition-colors"
                                title="预览切片"
                              >
                                <Eye className="w-4 h-4 text-text-tertiary" />
                              </button>
                              <button
                                onClick={() => handleDownload(doc)}
                                className="p-2 rounded-lg hover:bg-bg-secondary transition-colors"
                                title="下载"
                              >
                                <Download className="w-4 h-4 text-text-tertiary" />
                              </button>
                              <button
                                onClick={() => handleDeleteClick(doc)}
                                className="p-2 rounded-lg hover:bg-error-light transition-colors"
                                title="删除"
                              >
                                <Trash2 className="w-4 h-4 text-text-tertiary" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div className="col-span-12 lg:col-span-4 space-y-4">
          <Card padding="md" className="sticky top-4">
            <h3 className="font-semibold text-text-primary mb-4 flex items-center gap-2">
              <Search className="w-4 h-4 text-text-secondary" />
              快速检索
            </h3>

            <div className="space-y-3">
              <div className="p-3 rounded-xl bg-bg-secondary/50 border border-border/50">
                <div className="flex items-center gap-2 mb-2">
                  <BookOpen className="w-3 h-3 text-primary" />
                  <span className="text-xs font-medium text-text-primary">关键词检索</span>
                </div>
                <form
                  className="flex items-center gap-2"
                  onSubmit={(event) => { event.preventDefault(); void handleSliceSearch() }}
                >
                  <input
                    type="search"
                    value={sliceSearchQuery}
                    onChange={(event) => setSliceSearchQuery(event.target.value)}
                    placeholder="输入关键词搜索切片..."
                    className="min-w-0 flex-1 h-9 px-3 bg-bg-card border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                  <button
                    type="submit"
                    disabled={sliceSearchLoading}
                    title="搜索知识切片"
                    className="h-9 w-9 shrink-0 rounded-lg border border-border bg-bg-card flex items-center justify-center hover:border-primary/40 disabled:opacity-50"
                  >
                    <Search className="w-4 h-4 text-text-secondary" />
                  </button>
                </form>
                {sliceSearchLoading && <p className="text-xs text-text-tertiary mt-2">正在检索...</p>}
                {sliceSearchError && <p className="text-xs text-error mt-2">{sliceSearchError}</p>}
                {!sliceSearchLoading && !sliceSearchError && sliceSearchQuery.trim() && sliceSearchResults.length === 0 && (
                  <p className="text-xs text-text-tertiary mt-2">未找到匹配切片</p>
                )}
                {sliceSearchResults.length > 0 && (
                  <div className="mt-3 space-y-2 max-h-64 overflow-y-auto">
                    {sliceSearchResults.map((result) => (
                      <div key={`${result.docId}-${result.sliceIndex}`} className="p-2 rounded-lg bg-bg-card/50 border border-border/50">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-xs font-medium text-text-primary truncate">{result.docTitle}</span>
                          <span className="text-[11px] text-text-tertiary shrink-0">{Math.round(result.similarity * 100)}%</span>
                        </div>
                        <p className="text-xs text-text-secondary line-clamp-3">{result.highlightedContent || result.content}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="p-3 rounded-xl bg-bg-secondary/50 border border-border/50">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-text-primary flex items-center gap-1">
                    <Layers className="w-3 h-3" />
                    最近切片
                  </span>
                  <Badge variant="default" size="sm">实时</Badge>
                </div>
                <div className="space-y-2">
                  {knowledgeDocs.slice(0, 2).map((doc) => (
                    doc.contentPreview ? (
                      <div key={doc.id} className="p-2 rounded-lg bg-bg-card/50 text-xs text-text-secondary line-clamp-2">
                        {doc.contentPreview.slice(0, 60)}...
                      </div>
                    ) : null
                  ))}
                  {!knowledgeDocs.some(d => d.contentPreview) && (
                    <div className="p-2 rounded-lg bg-bg-card/50 text-xs text-text-tertiary text-center">
                      暂无切片预览
                    </div>
                  )}
                </div>
              </div>

              <div className="p-3 rounded-xl bg-success/5 border border-success/20">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-success flex items-center gap-1">
                    <CheckCircle className="w-3 h-3" />
                    索引完成率
                  </span>
                  <span className="text-sm font-semibold text-success">
                    {stats.totalSlices > 0 ? Math.round(stats.indexedSlices / stats.totalSlices * 100) : 0}%
                  </span>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>

      <UploadModal isOpen={showUpload} onClose={() => setShowUpload(false)} onSuccess={() => fetchKnowledgeDocs({ page: 1, pageSize: 50 })} />
      <DocPreviewModal
        isOpen={showPreview}
        onClose={() => { setShowPreview(false); setSelectedDoc(undefined) }}
        doc={selectedDoc}
        slices={knowledgeSlices}
        slicesLoading={slicesLoading}
        domainToLabel={domainToLabel}
      />
      <TraceabilityModal isOpen={showTraceability} onClose={() => setShowTraceability(false)} />

      {/* 删除确认弹窗 */}
      {showDeleteConfirm && deleteTarget && (
        <Modal isOpen={showDeleteConfirm} onClose={() => { setShowDeleteConfirm(false); setDeleteTarget(null) }} maxWidth="max-w-sm" className="p-8">
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-error/10 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-6 h-6 text-error" />
            </div>
            <h3 className="text-base font-semibold text-text-primary mb-2">确认删除文档？</h3>
            <p className="text-sm text-text-secondary mb-1">
              即将删除「<span className="font-medium text-text-primary">{deleteTarget.title}</span>」
            </p>
            <p className="text-xs text-text-tertiary mb-5">
              {deleteTarget.totalSlices} 个切片将被一并删除，此操作不可撤销
            </p>
            <div className="flex justify-center gap-2">
              <Button variant="outline" onClick={() => { setShowDeleteConfirm(false); setDeleteTarget(null) }}>取消</Button>
              <Button
                variant="primary"
                onClick={handleDeleteConfirm}
                disabled={deleting}
                className="!bg-error hover:!bg-error/90"
              >
                {deleting ? '删除中...' : '确认删除'}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
