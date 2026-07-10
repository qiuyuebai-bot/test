import type { StateCreator } from 'zustand'
import type { LearnerProfile } from '../types'
import { learnerApi } from '../api'
import type { AppState } from './index'

export interface LearnerSlice {
  learners: LearnerProfile[]
  currentLearner: LearnerProfile | null
  learnersLoading: boolean
  learnerLoading: boolean
  learnersTotal: number
  pagination: { page: number; pageSize: number; total: number; totalPages: number }
  fetchLearners: (params?: { page?: number; pageSize?: number; keyword?: string }) => Promise<void>
  fetchLearnerById: (id: number) => Promise<LearnerProfile>
  setCurrentLearner: (learner: LearnerProfile | null) => void
  createLearner: (data: Parameters<typeof learnerApi.create>[0]) => Promise<{ id: number }>
  addLearner: (data: Parameters<typeof learnerApi.create>[0]) => Promise<{ id: number }>
  updateLearner: (id: number, data: Partial<Parameters<typeof learnerApi.create>[0]>) => Promise<{ id: number }>
  deleteLearner: (id: number) => Promise<void>
}

let _latestLearnerReqId = 0

export const createLearnerSlice: StateCreator<AppState, [], [], LearnerSlice> = (set, get) => ({
  learners: [],
  currentLearner: null,
  learnersLoading: false,
  learnerLoading: false,
  learnersTotal: 0,
  pagination: { page: 1, pageSize: 20, total: 0, totalPages: 0 },

  fetchLearners: async (params) => {
    set({ learnersLoading: true, learnerLoading: true })
    try {
      const result = await learnerApi.getList({
        page: 1,
        pageSize: 20,
        ...params,
      })
      set({
        learners: result.items,
        learnersTotal: result.total,
        learnersLoading: false,
        learnerLoading: false,
        pagination: {
          page: result.page,
          pageSize: result.pageSize,
          total: result.total,
          totalPages: result.totalPages,
        },
      })
    } catch (err) {
      console.error('fetchLearners failed:', err)
      set({ learnersLoading: false, learnerLoading: false })
    }
  },

  fetchLearnerById: async (id: number) => {
    const reqId = ++_latestLearnerReqId
    const learner = await learnerApi.getById(id)
    if (reqId !== _latestLearnerReqId) return learner
    set({ currentLearner: learner })
    return learner
  },

  setCurrentLearner: (learner) => set({ currentLearner: learner }),

  createLearner: async (data) => {
    const result = await learnerApi.create(data)
    await get().fetchLearners({ page: get().pagination.page, pageSize: get().pagination.pageSize })
    return result
  },

  addLearner: async (data) => {
    return get().createLearner(data)
  },

  updateLearner: async (id, data) => {
    const result = await learnerApi.update(id, data)
    await get().fetchLearners({ page: get().pagination.page, pageSize: get().pagination.pageSize })
    const current = get().currentLearner
    if (current && current.id === id) {
      const updated = await learnerApi.getById(id)
      set({ currentLearner: updated })
    }
    return result
  },

  deleteLearner: async (id) => {
    await learnerApi.delete(id)
    const current = get().currentLearner
    if (current && current.id === id) {
      set({ currentLearner: null })
    }
    await get().fetchLearners({ page: get().pagination.page, pageSize: get().pagination.pageSize })
  },
})
