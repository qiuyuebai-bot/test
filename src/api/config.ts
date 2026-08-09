import { http } from '../lib/request'

export interface IndustryOption {
  value: string
  label: string
}

export interface DomainOption {
  value: string
  label: string
  color: string
}

export interface DesensitizationRule {
  field: string
  rule: string
  enabled: boolean
}

export interface BusinessConfig {
  industries: IndustryOption[]
  domains: DomainOption[]
  desensitizationRules: DesensitizationRule[]
}

export const configApi = {
  getOptions(): Promise<BusinessConfig> {
    return http.get<BusinessConfig>('/config/options')
  },
}
