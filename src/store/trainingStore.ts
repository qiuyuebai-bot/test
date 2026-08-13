import type { StateCreator } from 'zustand'
import { trainingApi } from '../api'
import type { AppState } from './index'
import type {
  Position, Competency, AssessmentRecord,
  Certification, CertificationRecord, TrainingProject,
  TrainingStageContext,
} from '../types/training'

export interface TrainingSlice {
  positions: Position[]
  positionsLoading: boolean
  competencies: Competency[]
  assessmentRecords: AssessmentRecord[]
  assessmentRecordsLoading: boolean
  certifications: Certification[]
  certificationRecords: CertificationRecord[]
  certificationRecordsLoading: boolean
  trainingProjects: TrainingProject[]
  trainingProjectsLoading: boolean
  activeTrainingContext: TrainingStageContext | null

  fetchPositions: (params?: { page?: number; pageSize?: number; keyword?: string }) => Promise<void>
  fetchCompetencies: () => Promise<void>
  fetchAssessmentRecords: (params?: { positionId?: number; learnerId?: number; status?: string }) => Promise<void>
  fetchCertifications: () => Promise<void>
  fetchCertificationRecords: (params?: { status?: string; learnerId?: number }) => Promise<void>
  fetchTrainingProjects: (params?: { status?: string; positionId?: number }) => Promise<void>
  setTrainingContext: (context: TrainingStageContext | null) => void
  clearTrainingContext: () => void
}

export const createTrainingSlice: StateCreator<AppState, [], [], TrainingSlice> = (set) => ({
  positions: [],
  positionsLoading: false,
  competencies: [],
  assessmentRecords: [],
  assessmentRecordsLoading: false,
  certifications: [],
  certificationRecords: [],
  certificationRecordsLoading: false,
  trainingProjects: [],
  trainingProjectsLoading: false,
  activeTrainingContext: null,

  fetchPositions: async (params) => {
    set({ positionsLoading: true })
    try {
      const result = await trainingApi.listPositions({
        page: params?.page ?? 1,
        page_size: params?.pageSize ?? 50,
        keyword: params?.keyword,
      })
      set({ positions: result.items, positionsLoading: false })
    } catch (err) {
      console.error('fetchPositions failed:', err)
      set({ positionsLoading: false })
    }
  },

  fetchCompetencies: async () => {
    try {
      const result = await trainingApi.listCompetencies({ page: 1, page_size: 100 })
      set({ competencies: result.items })
    } catch (err) {
      console.error('fetchCompetencies failed:', err)
    }
  },

  fetchAssessmentRecords: async (params) => {
    set({ assessmentRecordsLoading: true })
    try {
      const result = await trainingApi.listAssessmentRecords({
        page: 1,
        page_size: 50,
        learner_id: params?.learnerId,
        position_id: params?.positionId,
        status: params?.status,
      })
      set({ assessmentRecords: result.items, assessmentRecordsLoading: false })
    } catch (err) {
      console.error('fetchAssessmentRecords failed:', err)
      set({ assessmentRecordsLoading: false })
    }
  },

  fetchCertifications: async () => {
    try {
      const result = await trainingApi.listCertifications({ page: 1, page_size: 50 })
      set({ certifications: result.items })
    } catch (err) {
      console.error('fetchCertifications failed:', err)
    }
  },

  fetchCertificationRecords: async (params) => {
    set({ certificationRecordsLoading: true })
    try {
      const result = await trainingApi.listCertificationRecords({
        page: 1,
        page_size: 50,
        status: params?.status,
        learner_id: params?.learnerId,
      })
      set({ certificationRecords: result.items, certificationRecordsLoading: false })
    } catch (err) {
      console.error('fetchCertificationRecords failed:', err)
      set({ certificationRecordsLoading: false })
    }
  },

  fetchTrainingProjects: async (params) => {
    set({ trainingProjectsLoading: true })
    try {
      const result = await trainingApi.listTrainingProjects({
        page: 1,
        page_size: 50,
        status: params?.status,
        position_id: params?.positionId,
      })
      set({ trainingProjects: result.items, trainingProjectsLoading: false })
    } catch (err) {
      console.error('fetchTrainingProjects failed:', err)
      set({ trainingProjectsLoading: false })
    }
  },

  setTrainingContext: (context) => set({ activeTrainingContext: context }),
  clearTrainingContext: () => set({ activeTrainingContext: null }),
})
