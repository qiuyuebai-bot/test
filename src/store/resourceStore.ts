import type { StateCreator } from 'zustand'
import type { LearningResource } from '../types'
import { coreApi } from '../api'
import type { AppState } from './index'

export interface ResourceSlice {
  resources: LearningResource[]
  resourcesTotal: number
  resourcesLoading: boolean
  resourceLoading: boolean
  fetchResources: (params?: { page?: number; pageSize?: number; learnerId?: number }) => Promise<void>
  generateResources: (params: { learnerId: number; targetTopic: string; industry?: string }) => Promise<{ taskId: string }>
  generateResource: (params: { learnerId: number; resourceType: string; title: string }) => Promise<LearningResource>
}

export const createResourceSlice: StateCreator<AppState, [], [], ResourceSlice> = (set, get) => ({
  resources: [],
  resourcesTotal: 0,
  resourcesLoading: false,
  resourceLoading: false,

  fetchResources: async (params) => {
    set({ resourcesLoading: true, resourceLoading: true })
    try {
      const result = await coreApi.getResourceList({
        page: 1,
        pageSize: 50,
        ...params,
      })
      const mappedItems = result.items.map((item: LearningResource) => ({
        ...item,
        resourceType: item.resourceType as LearningResource['resourceType'],
        targetLearnerId: item.targetLearnerId ?? item.learnerId ?? 0,
        contentSummary: item.contentSummary ?? item.summary ?? '',
        contentPath: item.contentPath ?? undefined,
        contentType: (item.contentType || 'text') as LearningResource['contentType'],
        qualityScore: item.qualityScore ?? Math.round((item.matchScore || 0) * 100),
        hallucinationDetected: item.hallucinationDetected ?? item.hasHallucination ?? false,
        reviewStatus: (item.reviewStatus || 'pending') as LearningResource['reviewStatus'],
        versionNumber: item.versionNumber ?? item.version ?? 1,
        generatedByAgent: item.generatedByAgent ?? item.createdByAgent ?? 'generation-agent',
        generationTime: item.generationTime ?? item.createdAt ?? new Date().toISOString(),
        metaData: item.metaData ?? {},
      }))
      set({ resources: mappedItems, resourcesTotal: result.total, resourcesLoading: false, resourceLoading: false })
    } catch (err) {
      console.error('fetchResources failed:', err)
      set({ resourcesLoading: false, resourceLoading: false })
    }
  },

  generateResources: async (params) => {
    const result = await coreApi.generateResources(params)
    return result
  },

  generateResource: async (params) => {
    set({ resourceLoading: true })
    try {
      const result = await coreApi.generateResources({
        learnerId: params.learnerId,
        targetTopic: params.title,
      })
      await get().fetchResources({ page: 1, pageSize: 20 })
      set({ resourceLoading: false })
      return {
        id: Date.now(),
        title: params.title,
        resourceType: params.resourceType as LearningResource['resourceType'],
        targetLearnerId: params.learnerId,
        contentSummary: '',
        contentType: 'text',
        qualityScore: 0,
        hallucinationDetected: false,
        reviewStatus: 'pending',
        versionNumber: 1,
        generatedByAgent: 'generation-agent',
        generationTime: new Date().toISOString(),
        metaData: { taskId: result.taskId },
      }
    } catch (error) {
      set({ resourceLoading: false })
      throw error
    }
  },
})
