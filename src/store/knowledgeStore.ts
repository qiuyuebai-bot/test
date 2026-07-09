import type { StateCreator } from 'zustand'
import type { KnowledgeDoc, KnowledgeSlice } from '../types'
import { knowledgeApi } from '../api'
import type { AppState } from './index'

export interface KnowledgeSliceState {
  knowledgeDocs: KnowledgeDoc[]
  knowledgeSlices: KnowledgeSlice[]
  knowledgeLoading: boolean
  knowledgeError: string | null
  totalKnowledgeDocs: number
  currentPage: number
  pageSize: number
  fetchKnowledgeDocs: (params?: { page?: number; pageSize?: number; keyword?: string; industry?: string }) => Promise<void>
  fetchKnowledgeSlices: (docId: number, params?: { sliceStart?: number; sliceCount?: number }) => Promise<void>
}

let _latestSlicesReqId = 0

export const createKnowledgeSlice: StateCreator<AppState, [], [], KnowledgeSliceState> = (set) => ({
  knowledgeDocs: [],
  knowledgeSlices: [],
  knowledgeLoading: false,
  knowledgeError: null,
  totalKnowledgeDocs: 0,
  currentPage: 1,
  pageSize: 50,

  fetchKnowledgeDocs: async (params) => {
    set({ knowledgeLoading: true, knowledgeError: null })
    try {
      const result = await knowledgeApi.getList({
        page: 1,
        pageSize: 50,
        ...params,
      })
      set({
        knowledgeDocs: result.items,
        totalKnowledgeDocs: result.total,
        currentPage: result.page,
        pageSize: result.pageSize,
        knowledgeLoading: false,
      })
    } catch (err) {
      set({
        knowledgeLoading: false,
        knowledgeError: err instanceof Error ? err.message : '加载文档列表失败',
      })
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
