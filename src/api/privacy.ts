import { http } from '../lib/request'
import type {
  PrivacyComplianceItem,
  PrivacyAnonymizationRule,
  PrivacyPermissionItem,
  PrivacyKeyInfo,
  PrivacyDocument,
  PrivacyOverview,
  AnonymizationTestResult,
} from '../types'

export const privacyApi = {
  getOverview(): Promise<PrivacyOverview> {
    return http.get<PrivacyOverview>('/privacy/overview')
  },

  getCompliance(): Promise<PrivacyComplianceItem[]> {
    return http.get<PrivacyComplianceItem[]>('/privacy/compliance')
  },

  getAnonymization(): Promise<PrivacyAnonymizationRule[]> {
    return http.get<PrivacyAnonymizationRule[]>('/privacy/anonymization')
  },

  testAnonymization(field: string, value: string): Promise<AnonymizationTestResult> {
    return http.post<AnonymizationTestResult>('/privacy/anonymization/test', { field, value })
  },

  getPermissions(): Promise<PrivacyPermissionItem[]> {
    return http.get<PrivacyPermissionItem[]>('/privacy/permissions')
  },

  getKeys(): Promise<PrivacyKeyInfo[]> {
    return http.get<PrivacyKeyInfo[]>('/privacy/keys')
  },

  getDocuments(): Promise<PrivacyDocument[]> {
    return http.get<PrivacyDocument[]>('/privacy/documents')
  },
}
