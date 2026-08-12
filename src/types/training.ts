// ============ Position 域 ============
export interface Competency {
  id: number
  code: string
  name: string
  category?: string
  description?: string
  level_descriptions?: Record<string, string>
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PositionCompetency {
  id: number
  position_id: number
  competency_id: number
  competency_name?: string
  competency_code?: string
  competency_category?: string
  required_level: number
  weight: number
  is_mandatory: boolean
  created_at: string
  // http 客户端 keysToCamel 转换后的运行时字段（与上方 snake_case 互为兼容）
  positionId?: number
  competencyId?: number
  competencyName?: string
  competencyCode?: string
  competencyCategory?: string
  requiredLevel?: number
  isMandatory?: boolean
  createdAt?: string
}

export interface Position {
  id: number
  code: string
  name: string
  category?: string
  industry?: string
  level?: string
  description?: string
  responsibilities?: string[]
  prerequisites?: string[]
  career_path?: string[]
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PositionDetail extends Position {
  competencies: PositionCompetency[]
}

// ============ Assessment 域 ============
export interface CompetencyConfig {
  competency_id: number
  question_count: number
  difficulty: number
  assessment_method: string
}

export interface AssessmentTemplate {
  id: number
  position_id: number
  name: string
  description?: string
  competency_configs: CompetencyConfig[]
  pass_threshold: number
  duration_minutes?: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CompetencyScore {
  id: number
  assessment_record_id: number
  competency_id: number
  competency_name?: string
  competency_code?: string
  current_level?: number
  current_score?: number
  required_level: number
  gap?: number
  assessment_method?: string
  evidence?: unknown[]
  created_at: string
}

export interface AssessmentRecord {
  id: number
  template_id: number
  user_id: number
  learner_id?: number
  position_id: number
  status: string
  overall_score?: number
  overall_level?: number
  gap_summary?: Array<{
    competency_id: number
    competency_name: string
    current_level: number
    required_level: number
    gap: number
  }>
  ai_diagnosis?: string
  started_at?: string
  completed_at?: string
  created_at: string
  updated_at: string
}

export interface AssessmentRecordDetail extends AssessmentRecord {
  competency_scores: CompetencyScore[]
  template_name?: string
  position_name?: string
}

export interface GapItem {
  competency_id: number
  competency_name: string
  competency_code?: string
  current_level?: number
  required_level: number
  gap: number
  is_met: boolean
}

export interface GapAnalysis {
  record_id: number
  overall_score?: number
  overall_level?: number
  pass_threshold: number
  is_passed: boolean
  total_competencies: number
  met_count: number
  gap_count: number
  gaps: GapItem[]
}

// ============ Certification 域 ============
export interface Certification {
  id: number
  position_id: number
  name: string
  code: string
  level?: string
  description?: string
  validity_period_months: number
  issuer?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CertificationRecord {
  id: number
  certification_id: number
  user_id: number
  learner_id?: number
  assessment_record_id: number
  status: string
  certificate_number?: string
  issued_at?: string
  expires_at?: string
  reviewed_by?: number
  review_comment?: string
  created_at: string
  updated_at: string
}

// ============ Training 域 ============
export interface TrainingProject {
  id: number
  name: string
  description?: string
  position_id: number
  certification_id?: number
  project_type?: string
  enterprise_name?: string
  status: string
  start_date?: string
  end_date?: string
  config?: Record<string, unknown>
  created_by?: number
  created_at: string
  updated_at: string
}

export interface TrainingEnrollment {
  id: number
  project_id: number
  user_id: number
  learner_id?: number
  status: string
  enrolled_at?: string
  completed_at?: string
  final_score?: number
  certification_record_id?: number
  created_at: string
  updated_at: string
}

export interface PlanStage {
  stage: number
  title: string
  competency_ids: number[]
  resources: unknown[]
  estimated_hours: number
  target_level: number
  deadline?: string | null
  description?: string
}

export interface TrainingPlan {
  id: number
  project_id: number
  enrollment_id: number
  user_id: number
  learner_id?: number
  assessment_record_id: number
  plan_content: PlanStage[]
  total_stages: number
  completed_stages: number
  progress: number
  status: string
  generated_by_ai: boolean
  created_at: string
  updated_at: string
}
