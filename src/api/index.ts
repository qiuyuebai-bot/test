export { authApi } from './auth'
export { learnerApi } from './learner'
export { domainToIndustry, knowledgeApi } from './knowledge'
export { agentApi } from './agent'
export { coreApi } from './core'
export { privacyApi } from './privacy'
export { configApi } from './config'
export { trainingApi } from './training'
export { dashboardApi } from './dashboard'
export { diagnosticApi } from './diagnostic'
export type {
  DiagnosticQuestion,
  DiagnosticSession,
  DiagnosticAssessment,
  DiagnosticAnswerResult,
} from './diagnostic'
export { aiConfigApi, AI_PROVIDER_OPTIONS } from './aiConfig'
export { desktopApi } from './desktop'
export type {
  AiConfig,
  AiConfigTestRequest,
  AiConfigTestResult,
  AiConfigUpdateRequest,
  AiGenerationParamsState,
  AiProviderGroup,
  AiProviderOption,
  AiProtocol,
} from './aiConfig'
