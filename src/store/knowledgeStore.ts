import type { StateCreator } from 'zustand'
import type { KnowledgeDoc, KnowledgeSlice } from '../types'
import { knowledgeApi } from '../api'
import type { KnowledgeStats } from '../api/knowledge'
import type { AppState } from './index'

export interface KnowledgeSliceState {
  knowledgeDocs: KnowledgeDoc[]
  knowledgeSlices: KnowledgeSlice[]
  knowledgeLoading: boolean
  knowledgeError: string | null
  totalKnowledgeDocs: number
  totalKnowledgePages: number
  knowledgeStats: KnowledgeStats | null
  knowledgeStatsLoading: boolean
  currentPage: number
  pageSize: number
  fetchKnowledgeDocs: (params?: { page?: number; pageSize?: number; keyword?: string; industry?: string }) => Promise<void>
  fetchKnowledgeStats: () => Promise<void>
  fetchKnowledgeSlices: (docId: number, params?: { sliceStart?: number; sliceCount?: number }) => Promise<void>
}

let _latestSlicesReqId = 0
let _latestDocsReqId = 0
let _latestStatsReqId = 0

export const createKnowledgeSlice: StateCreator<AppState, [], [], KnowledgeSliceState> = (set) => ({
  knowledgeDocs: [],
  knowledgeSlices: [],
  knowledgeLoading: false,
  knowledgeError: null,
  totalKnowledgeDocs: 0,
  totalKnowledgePages: 0,
  knowledgeStats: null,
  knowledgeStatsLoading: false,
  currentPage: 1,
  pageSize: 20,

  fetchKnowledgeDocs: async (params) => {
    const reqId = ++_latestDocsReqId
    set({ knowledgeLoading: true, knowledgeError: null })
    try {
      const result = await knowledgeApi.getList({
        page: 1,
        pageSize: 20,
        ...params,
      })
      if (reqId !== _latestDocsReqId) return
      set({
        knowledgeDocs: result.items,
        totalKnowledgeDocs: result.total,
        totalKnowledgePages: result.totalPages,
        currentPage: result.page,
        pageSize: result.pageSize,
        knowledgeLoading: false,
      })
    } catch (err) {
      if (reqId !== _latestDocsReqId) return
      set({
        knowledgeLoading: false,
        knowledgeError: err instanceof Error ? err.message : '加载文档列表失败',
      })
    }
  },

  fetchKnowledgeStats: async () => {
    const reqId = ++_latestStatsReqId
    set({ knowledgeStatsLoading: true })
    try {
      const stats = await knowledgeApi.getStats()
      if (reqId !== _latestStatsReqId) return
      set({ knowledgeStats: stats, knowledgeStatsLoading: false })
    } catch {
      if (reqId !== _latestStatsReqId) return
      set({ knowledgeStatsLoading: false })
    }
  },

  fetchKnowledgeSlices: async (docId, params) => {
    const reqId = ++_latestSlicesReqId
    set({ knowledgeLoading: true, knowledgeError: null })
    try {
      const slices = await knowledgeApi.getSlices(docId, params)
      if (reqId !== _latestSlicesReqId) return
      set({ knowledgeSlices: slices, knowledgeLoading: false })
    } catch (err) {
      if (reqId !== _latestSlicesReqId) return
      set({
        knowledgeLoading: false,
        knowledgeError: err instanceof Error ? err.message : '加载切片失败',
      })
    }
  },
})
