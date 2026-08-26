import type { StateCreator } from 'zustand'
import type { LearnerProfile } from '../types'
import { learnerApi } from '../api'
import type { AppState } from './index'
import { reportError } from '../lib/sentry'

export interface LearnerSlice {
  learners: LearnerProfile[]
  currentLearner: LearnerProfile | null
  learnersLoading: boolean
  learnerLoading: boolean
  learnerError: string | null
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
let _latestLearnersReqId = 0

export const createLearnerSlice: StateCreator<AppState, [], [], LearnerSlice> = (set, get) => ({
  learners: [],
  currentLearner: null,
  learnersLoading: false,
  learnerLoading: false,
  learnerError: null,
  learnersTotal: 0,
  pagination: { page: 1, pageSize: 20, total: 0, totalPages: 0 },

  fetchLearners: async (params) => {
    const reqId = ++_latestLearnersReqId
    set({ learnersLoading: true, learnerLoading: true, learnerError: null })
    try {
      const user = get().user
      const canReadLearnerList = user?.role === 'admin' || user?.role === 'teacher'

      if (!canReadLearnerList && user) {
        const learner = await learnerApi.getCurrent()
        if (reqId !== _latestLearnersReqId) return
        set({
          learners: [learner],
          currentLearner: learner,
          learnersTotal: 1,
          learnersLoading: false,
          learnerLoading: false,
          pagination: { page: 1, pageSize: 1, total: 1, totalPages: 1 },
        })
        return
      }

      const result = await learnerApi.getList({
        page: 1,
        pageSize: 20,
        ...params,
      })
      if (reqId !== _latestLearnersReqId) return
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
      if (reqId !== _latestLearnersReqId) return
      reportError(err, { tags: { area: 'learner', action: 'fetch_list' } })
      set({
        learnersLoading: false,
        learnerLoading: false,
        learnerError: err instanceof Error ? err.message : '学习者画像加载失败',
      })
    }
  },

  fetchLearnerById: async (id: number) => {
    const reqId = ++_latestLearnerReqId
    const learner = await learnerApi.getById(id)
    if (reqId !== _latestLearnerReqId) return learner
    set((state) => ({
      currentLearner: learner,
      learners: state.learners.map((item) => item.id === learner.id ? learner : item),
      learnerError: null,
    }))
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
