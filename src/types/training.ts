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
  isActive?: boolean
  createdAt?: string
  updatedAt?: string
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
  // http 客户端 keysToCamel 转换后的运行时字段
  competencyId?: number
  questionCount?: number
  assessmentMethod?: string
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
  // http 客户端 keysToCamel 转换后的运行时字段
  positionId?: number
  competencyConfigs?: CompetencyConfig[]
  passThreshold?: number
  durationMinutes?: number
  isActive?: boolean
  createdAt?: string
  updatedAt?: string
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
  competencyId?: number
  competencyName?: string
  competencyCode?: string
  currentLevel?: number
  currentScore?: number
  requiredLevel?: number
  assessmentMethod?: string
  createdAt?: string
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
  // http 客户端 keysToCamel 转换后的运行时字段
  templateId?: number
  userId?: number
  learnerId?: number
  positionId?: number
  overallScore?: number
  overallLevel?: number
  gapSummary?: Array<{
    competencyId: number
    competencyName: string
    currentLevel: number
    requiredLevel: number
    gap: number
  }>
  aiDiagnosis?: string
  startedAt?: string
  completedAt?: string
  createdAt?: string
  updatedAt?: string
}

export interface AssessmentRecordDetail extends AssessmentRecord {
  competency_scores: CompetencyScore[]
  template_name?: string
  position_name?: string
  competencyScores?: CompetencyScore[]
  templateName?: string
  positionName?: string
}

export interface GapItem {
  competency_id: number
  competency_name: string
  competency_code?: string
  current_level?: number
  required_level: number
  gap: number
  is_met: boolean
  competencyId?: number
  competencyName?: string
  competencyCode?: string
  currentLevel?: number
  requiredLevel?: number
  isMet?: boolean
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
  recordId?: number
  overallScore?: number
  overallLevel?: number
  passThreshold?: number
  isPassed?: boolean
  totalCompetencies?: number
  metCount?: number
  gapCount?: number
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
  positionId?: number
  validityPeriodMonths?: number
  isActive?: boolean
  createdAt?: string
  updatedAt?: string
}

export interface CertificationRule {
  id: number
  certification_id: number
  rule_type: string
  rule_config: Record<string, unknown>
  created_at: string
  certificationId?: number
  ruleType?: string
  ruleConfig?: Record<string, unknown>
  createdAt?: string
}

export interface CertificationDetail extends Certification {
  rules: CertificationRule[]
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
  rule_evaluation?: Record<string, unknown>
  created_at: string
  updated_at: string
  certificationId?: number
  userId?: number
  learnerId?: number
  assessmentRecordId?: number
  certificateNumber?: string
  issuedAt?: string
  expiresAt?: string
  reviewedBy?: number
  reviewComment?: string
  ruleEvaluation?: Record<string, unknown>
  createdAt?: string
  updatedAt?: string
}

export interface CertificationRecordDetail extends CertificationRecord {
  certification_name?: string
  certification_code?: string
  assessment_score?: number
  assessment_level?: number
  certificationName?: string
  certificationCode?: string
  assessmentScore?: number
  assessmentLevel?: number
}

export interface CertificationVerification {
  certificate_number?: string
  status: string
  is_valid?: boolean
  certification_name?: string
  certification_code?: string
  certification_level?: string
  issuer?: string
  learner_name?: string
  issued_at?: string
  expires_at?: string
  certificateNumber?: string
  isValid?: boolean
  certificationName?: string
  certificationCode?: string
  certificationLevel?: string
  learnerName?: string
  issuedAt?: string
  expiresAt?: string
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
  position_name?: string
  certification_name?: string
  enrollment_count?: number
  // http 客户端 keysToCamel 转换后的运行时字段
  positionId?: number
  certificationId?: number
  projectType?: string
  enterpriseName?: string
  startDate?: string
  endDate?: string
  createdBy?: number
  createdAt?: string
  updatedAt?: string
  positionName?: string
  certificationName?: string
  enrollmentCount?: number
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
  // http 客户端 keysToCamel 转换后的运行时字段
  projectId?: number
  userId?: number
  learnerId?: number
  enrolledAt?: string
  completedAt?: string
  finalScore?: number
  certificationRecordId?: number
  createdAt?: string
  updatedAt?: string
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
  // http 客户端 keysToCamel 转换后的运行时字段
  competencyIds?: number[]
  estimatedHours?: number
  targetLevel?: number
}

export interface TrainingStageContext {
  projectId: number
  enrollmentId: number
  planId: number
  positionId: number
  learnerId?: number
  assessmentRecordId?: number
  stage: PlanStage
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
  // http 客户端 keysToCamel 转换后的运行时字段
  projectId?: number
  enrollmentId?: number
  userId?: number
  learnerId?: number
  assessmentRecordId?: number
  planContent?: PlanStage[]
  totalStages?: number
  completedStages?: number
  generatedByAi?: boolean
  createdAt?: string
  updatedAt?: string
}
