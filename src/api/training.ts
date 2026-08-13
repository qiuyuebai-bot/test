import { http, PagedData } from '../lib/request'
import type {
  Position, PositionDetail, Competency, PositionCompetency,
  AssessmentTemplate, AssessmentRecord, AssessmentRecordDetail, GapAnalysis,
  Certification, CertificationRecord,
  TrainingProject, TrainingEnrollment, TrainingPlan,
} from '../types/training'

type ListParams = { page?: number; page_size?: number; keyword?: string }

// ============ Position 域 ============
export const trainingApi = {
  // ---- 岗位 ----
  listPositions(params?: ListParams & { category?: string; level?: string }): Promise<PagedData<Position>> {
    return http.get<PagedData<Position>>('/positions', {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 20,
      keyword: params?.keyword,
      category: params?.category,
      level: params?.level,
    })
  },

  getPosition(id: number): Promise<PositionDetail> {
    return http.get<PositionDetail>(`/positions/${id}`)
  },

  createPosition(data: Partial<Position> & { code: string; name: string }): Promise<Position> {
    return http.post<Position>('/positions', data)
  },

  updatePosition(id: number, data: Partial<Position>): Promise<Position> {
    return http.put<Position>(`/positions/${id}`, data)
  },

  deletePosition(id: number): Promise<void> {
    return http.delete<void>(`/positions/${id}`)
  },

  addPositionCompetency(positionId: number, data: {
    competency_id: number; required_level: number; weight?: number; is_mandatory?: boolean
  }): Promise<PositionCompetency> {
    return http.post<PositionCompetency>(`/positions/${positionId}/competencies`, data)
  },

  removePositionCompetency(positionId: number, competencyId: number): Promise<void> {
    return http.delete<void>(`/positions/${positionId}/competencies/${competencyId}`)
  },

  // ---- 胜任力 ----
  listCompetencies(params?: ListParams & { category?: string }): Promise<PagedData<Competency>> {
    return http.get<PagedData<Competency>>('/competencies', {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 50,
      keyword: params?.keyword,
      category: params?.category,
    })
  },

  createCompetency(data: { code: string; name: string; category?: string; description?: string }): Promise<Competency> {
    return http.post<Competency>('/competencies', data)
  },

  deleteCompetency(id: number): Promise<void> {
    return http.delete<void>(`/competencies/${id}`)
  },

  // ============ Assessment 域 ============
  listAssessmentTemplates(params?: ListParams & { position_id?: number }): Promise<PagedData<AssessmentTemplate>> {
    return http.get<PagedData<AssessmentTemplate>>('/assessments/templates', {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 20,
      position_id: params?.position_id,
      keyword: params?.keyword,
    })
  },

  createAssessmentTemplate(data: {
    position_id: number; name: string; description?: string;
    competency_configs: Array<{
      competency_id: number; question_count: number; difficulty: number; assessment_method: string
    }>;
    pass_threshold?: number; duration_minutes?: number
  }): Promise<AssessmentTemplate> {
    return http.post<AssessmentTemplate>('/assessments/templates', data)
  },

  startAssessment(data: { template_id: number; learner_id?: number }): Promise<AssessmentRecord> {
    return http.post<AssessmentRecord>('/assessments/start', data)
  },

  listAssessmentRecords(params?: ListParams & { user_id?: number; position_id?: number; status?: string }): Promise<PagedData<AssessmentRecord>> {
    return http.get<PagedData<AssessmentRecord>>('/assessments/records', {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 20,
      user_id: params?.user_id,
      position_id: params?.position_id,
      status: params?.status,
    })
  },

  getAssessmentRecord(id: number): Promise<AssessmentRecordDetail> {
    return http.get<AssessmentRecordDetail>(`/assessments/records/${id}`)
  },

  submitAssessment(id: number, data: {
    scores: Array<{
      competency_id: number; current_level: number; current_score: number;
      assessment_method: string; evidence?: unknown[]
    }>
  }): Promise<AssessmentRecord> {
    return http.post<AssessmentRecord>(`/assessments/records/${id}/submit`, data)
  },

  getGapAnalysis(recordId: number): Promise<GapAnalysis> {
    return http.get<GapAnalysis>(`/assessments/records/${recordId}/gaps`)
  },

  // ============ Certification 域 ============
  listCertifications(params?: ListParams): Promise<PagedData<Certification>> {
    return http.get<PagedData<Certification>>('/certifications', {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 20,
      keyword: params?.keyword,
    })
  },

  createCertification(data: {
    position_id: number; name: string; code: string; level?: string;
    description?: string; validity_period_months?: number; issuer?: string
  }): Promise<Certification> {
    return http.post<Certification>('/certifications', data)
  },

  applyCertification(data: {
    certification_id: number; assessment_record_id: number; learner_id?: number
  }): Promise<CertificationRecord> {
    return http.post<CertificationRecord>('/certifications/apply', data)
  },

  listCertificationRecords(params?: ListParams & { status?: string; user_id?: number }): Promise<PagedData<CertificationRecord>> {
    return http.get<PagedData<CertificationRecord>>('/certifications/records/list', {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 20,
      status: params?.status,
      user_id: params?.user_id,
    })
  },

  approveCertification(recordId: number, data: { comment?: string }): Promise<CertificationRecord> {
    return http.post<CertificationRecord>(`/certifications/records/${recordId}/approve`, data)
  },

  rejectCertification(recordId: number, data: { comment?: string }): Promise<CertificationRecord> {
    return http.post<CertificationRecord>(`/certifications/records/${recordId}/reject`, data)
  },

  // ============ Training 域 ============
  listTrainingProjects(params?: ListParams & { status?: string; position_id?: number }): Promise<PagedData<TrainingProject>> {
    return http.get<PagedData<TrainingProject>>('/training-projects', {
      page: params?.page ?? 1,
      page_size: params?.page_size ?? 20,
      keyword: params?.keyword,
      status: params?.status,
      position_id: params?.position_id,
    })
  },

  createTrainingProject(data: {
    name: string; description?: string; position_id: number; certification_id?: number;
    project_type?: string; enterprise_name?: string;
    start_date?: string; end_date?: string; config?: Record<string, unknown>
  }): Promise<TrainingProject> {
    return http.post<TrainingProject>('/training-projects', data)
  },

  getTrainingProject(id: number): Promise<TrainingProject> {
    return http.get<TrainingProject>(`/training-projects/${id}`)
  },

  updateTrainingProject(id: number, data: Partial<TrainingProject>): Promise<TrainingProject> {
    return http.put<TrainingProject>(`/training-projects/${id}`, data)
  },

  enrollProject(projectId: number, data: { learner_id?: number }): Promise<TrainingEnrollment> {
    return http.post<TrainingEnrollment>(`/training-projects/${projectId}/enroll`, data)
  },

  listProjectEnrollments(projectId: number): Promise<PagedData<TrainingEnrollment>> {
    return http.get<PagedData<TrainingEnrollment>>(`/training-projects/${projectId}/enrollments`)
  },

  generatePlan(enrollmentId: number, data: { assessment_record_id: number }): Promise<TrainingPlan> {
    return http.post<TrainingPlan>(`/training-enrollments/${enrollmentId}/generate-plan`, data, {
      timeout: 120000, silent: true,
    })
  },

  getPlan(enrollmentId: number): Promise<TrainingPlan> {
    return http.get<TrainingPlan>(`/training-enrollments/${enrollmentId}/plan`)
  },

  updateProgress(planId: number, data: { completed_stages: number }): Promise<TrainingPlan> {
    return http.put<TrainingPlan>(`/training-plans/${planId}/progress`, data)
  },

  completeTraining(enrollmentId: number): Promise<TrainingEnrollment> {
    return http.post<TrainingEnrollment>(`/training-enrollments/${enrollmentId}/complete`, {})
  },
}
