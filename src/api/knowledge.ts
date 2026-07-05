import { http, PagedData } from '../lib/request'
import type { KnowledgeDoc, KnowledgeSlice, KnowledgeSearchResponse, PaginationParams } from '../types'

export interface KnowledgeListParams extends PaginationParams {
  keyword?: string
  industry?: string
  status?: string
}

const industryToDomain: Record<string, string> = {
  '智能制造': 'smart_manufacturing',
  '工业互联网': 'industrial_internet',
  '软件开发': 'software_development',
  '人工智能训练': 'artificial_intelligence',
  '人工智能': 'artificial_intelligence',
  '数据分析': 'data_analysis',
  '通用': 'general',
}

const statusMap: Record<string, 'indexed' | 'pending' | 'error'> = {
  'ready': 'indexed',
  'processing': 'pending',
  'uploading': 'pending',
  'error': 'error',
}

interface RawDoc {
  id: number
  title: string
  industry: string
  category?: string
  fileName: string
  fileType?: string
  fileSize?: number
  totalPages?: number
  wordCount?: number
  sliceCount: number
  indexedSliceCount: number
  coverageRate?: number
  status: string
  version: string
  source?: string
  author?: string
  tags?: string[]
  isEnabled?: boolean
  contentPreview?: string
  createdAt?: string
  updatedAt?: string
  indexedAt?: string
}

interface RawSlice {
  id: number
  docId: number
  sliceIndex: number
  content: string
  sliceType?: string
  title?: string
  wordCount?: number
  keywords?: string[]
  isIndexed?: boolean
  qualityScore?: number
  referenceCount?: number
  createdAt?: string
}

function mapDocFromApi(raw: RawDoc): KnowledgeDoc {
  const domain = industryToDomain[raw.industry] || 'general'
  const rawStatus = raw.status || 'uploading'
  return {
    id: raw.id,
    title: raw.title,
    domain,
    category: raw.industry,
    totalSlices: raw.sliceCount || 0,
    indexedSlices: raw.indexedSliceCount || 0,
    status: statusMap[rawStatus] || 'pending',
    source: raw.source,
    uploadTime: raw.createdAt || '',
    fileType: raw.fileType,
    fileSize: raw.fileSize,
    version: raw.version || '1.0',
    fileName: raw.fileName,
    industry: raw.industry,
    coverageRate: raw.coverageRate,
    tags: raw.tags,
    author: raw.author,
    isEnabled: raw.isEnabled,
    contentPreview: raw.contentPreview,
    createdAt: raw.createdAt,
    updatedAt: raw.updatedAt,
    indexedAt: raw.indexedAt,
  }
}

function mapSliceFromApi(raw: RawSlice): KnowledgeSlice {
  return {
    id: raw.id,
    docId: raw.docId,
    sliceIndex: raw.sliceIndex,
    content: raw.content,
    contentType: raw.sliceType,
    sliceType: raw.sliceType,
    title: raw.title,
    wordCount: raw.wordCount,
    keywords: raw.keywords || [],
    isIndexed: raw.isIndexed,
    qualityScore: raw.qualityScore,
    referenceCount: raw.referenceCount,
    createdAt: raw.createdAt,
  }
}

export const knowledgeApi = {
  async getList(params?: KnowledgeListParams): Promise<PagedData<KnowledgeDoc>> {
    const result = await http.get<{
      items: RawDoc[]
      total: number
      page: number
      pageSize: number
      totalPages: number
    }>('/knowledge/docs', params as Record<string, string | number | boolean | undefined>)
    return {
      items: (result.items || []).map(mapDocFromApi),
      total: result.total || 0,
      page: result.page || 1,
      pageSize: result.pageSize || 50,
      totalPages: result.totalPages || 0,
    }
  },

  async getById(id: number): Promise<KnowledgeDoc> {
    const raw = await http.get<RawDoc>(`/knowledge/docs/${id}`)
    return mapDocFromApi(raw)
  },

  async getSlices(docId: number, params?: { sliceStart?: number; sliceCount?: number }): Promise<KnowledgeSlice[]> {
    const result = await http.get<{ slices: RawSlice[] }>(
      `/knowledge/preview/${docId}`,
      params as Record<string, string | number | boolean | undefined>
    )
    return (result.slices || []).map(mapSliceFromApi)
  },

  uploadText(data: { title: string; industry: string; content: string; category?: string; source?: string; author?: string }): Promise<{ docId: number; fileName: string; fileSize: number; status: string; message: string }> {
    return http.post('/knowledge/upload', data)
  },

  update(id: number, data: Partial<Pick<KnowledgeDoc, 'title' | 'category' | 'source'>>): Promise<{ id: number }> {
    return http.put<{ id: number }>(`/knowledge/docs/${id}`, data)
  },

  delete(id: number): Promise<null> {
    return http.delete<null>(`/knowledge/docs/${id}`)
  },

  search(data: { query: string; industry?: string; docId?: number; topK?: number; minSimilarity?: number }): Promise<KnowledgeSearchResponse> {
    return http.post<KnowledgeSearchResponse>('/knowledge/search', data)
  },

  getPreview(id: number, params?: { sliceStart?: number; sliceCount?: number }): Promise<unknown> {
    return http.get(`/knowledge/preview/${id}`, params as Record<string, string | number | boolean | undefined>)
  },

  traceResource(resourceId: number): Promise<unknown> {
    return http.get(`/knowledge/trace/${resourceId}`)
  },

  getIndustryStats(): Promise<unknown> {
    return http.get('/knowledge/stats/industries')
  },
}
