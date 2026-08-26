import type { StateCreator } from 'zustand'
import { trainingApi } from '../api'
import type { AppState } from './index'
import { reportError } from '../lib/sentry'
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

let _latestPositionsReqId = 0
let _latestCompetenciesReqId = 0
let _latestAssessmentRecordsReqId = 0
let _latestCertificationsReqId = 0
let _latestCertificationRecordsReqId = 0
let _latestTrainingProjectsReqId = 0

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
    const reqId = ++_latestPositionsReqId
    set({ positionsLoading: true })
    try {
      const result = await trainingApi.listPositions({
        page: params?.page ?? 1,
        page_size: params?.pageSize ?? 50,
        keyword: params?.keyword,
      })
      if (reqId !== _latestPositionsReqId) return
      set({ positions: result.items, positionsLoading: false })
    } catch (err) {
      if (reqId !== _latestPositionsReqId) return
      reportError(err, { tags: { area: 'training', action: 'fetch_positions' } })
      set({ positionsLoading: false })
    }
  },

  fetchCompetencies: async () => {
    const reqId = ++_latestCompetenciesReqId
    try {
      const result = await trainingApi.listCompetencies({ page: 1, page_size: 100 })
      if (reqId !== _latestCompetenciesReqId) return
      set({ competencies: result.items })
    } catch (err) {
      if (reqId !== _latestCompetenciesReqId) return
      reportError(err, { tags: { area: 'training', action: 'fetch_competencies' } })
    }
  },

  fetchAssessmentRecords: async (params) => {
    const reqId = ++_latestAssessmentRecordsReqId
    set({ assessmentRecordsLoading: true })
    try {
      const result = await trainingApi.listAssessmentRecords({
        page: 1,
        page_size: 50,
        learner_id: params?.learnerId,
        position_id: params?.positionId,
        status: params?.status,
      })
      if (reqId !== _latestAssessmentRecordsReqId) return
      set({ assessmentRecords: result.items, assessmentRecordsLoading: false })
    } catch (err) {
      if (reqId !== _latestAssessmentRecordsReqId) return
      reportError(err, { tags: { area: 'training', action: 'fetch_assessment_records' } })
      set({ assessmentRecordsLoading: false })
    }
  },

  fetchCertifications: async () => {
    const reqId = ++_latestCertificationsReqId
    try {
      const result = await trainingApi.listCertifications({ page: 1, page_size: 50 })
      if (reqId !== _latestCertificationsReqId) return
      set({ certifications: result.items })
    } catch (err) {
      if (reqId !== _latestCertificationsReqId) return
      reportError(err, { tags: { area: 'training', action: 'fetch_certifications' } })
    }
  },

  fetchCertificationRecords: async (params) => {
    const reqId = ++_latestCertificationRecordsReqId
    set({ certificationRecordsLoading: true })
    try {
      const result = await trainingApi.listCertificationRecords({
        page: 1,
        page_size: 50,
        status: params?.status,
        learner_id: params?.learnerId,
      })
      if (reqId !== _latestCertificationRecordsReqId) return
      set({ certificationRecords: result.items, certificationRecordsLoading: false })
    } catch (err) {
      if (reqId !== _latestCertificationRecordsReqId) return
      reportError(err, { tags: { area: 'training', action: 'fetch_certification_records' } })
      set({ certificationRecordsLoading: false })
    }
  },

  fetchTrainingProjects: async (params) => {
    const reqId = ++_latestTrainingProjectsReqId
    set({ trainingProjectsLoading: true })
    try {
      const result = await trainingApi.listTrainingProjects({
        page: 1,
        page_size: 50,
        status: params?.status,
        position_id: params?.positionId,
      })
      if (reqId !== _latestTrainingProjectsReqId) return
      set({ trainingProjects: result.items, trainingProjectsLoading: false })
    } catch (err) {
      if (reqId !== _latestTrainingProjectsReqId) return
      reportError(err, { tags: { area: 'training', action: 'fetch_training_projects' } })
      set({ trainingProjectsLoading: false })
    }
  },

  setTrainingContext: (context) => set({ activeTrainingContext: context }),
  clearTrainingContext: () => set({ activeTrainingContext: null }),
})
