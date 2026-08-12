import { useEffect, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import { trainingApi } from '@/api'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Modal from '@/components/Modal'
import LoadingState from '@/components/LoadingState'
import type { Certification, AssessmentRecord } from '@/types/training'

const STATUS_LABEL: Record<string, string> = {
  pending: '待审核', approved: '已批准', rejected: '已拒绝', expired: '已过期', revoked: '已撤销',
}
const STATUS_VARIANT: Record<string, 'default' | 'info' | 'success' | 'error'> = {
  pending: 'default', approved: 'success', rejected: 'error', expired: 'default', revoked: 'error',
}

export default function CertificationTab() {
  const {
    certifications, certificationRecords, certificationRecordsLoading,
    assessmentRecords, fetchCertifications, fetchCertificationRecords, fetchAssessmentRecords, user,
  } = useStore(
    useShallow((s) => ({
      certifications: s.certifications,
      certificationRecords: s.certificationRecords,
      certificationRecordsLoading: s.certificationRecordsLoading,
      assessmentRecords: s.assessmentRecords,
      fetchCertifications: s.fetchCertifications,
      fetchCertificationRecords: s.fetchCertificationRecords,
      fetchAssessmentRecords: s.fetchAssessmentRecords,
      user: s.user,
    })),
  )
  const [applyTarget, setApplyTarget] = useState<Certification | null>(null)
  const [selectedRecord, setSelectedRecord] = useState<AssessmentRecord | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const canReview = user?.role === 'admin' || user?.role === 'teacher'

  useEffect(() => {
    void fetchCertifications()
    void fetchCertificationRecords()
    void fetchAssessmentRecords()
  }, [fetchCertifications, fetchCertificationRecords, fetchAssessmentRecords])

  const handleApply = async () => {
    if (!applyTarget || !selectedRecord) return
    setSubmitting(true)
    try {
      await trainingApi.applyCertification({
        certification_id: applyTarget.id,
        assessment_record_id: selectedRecord.id,
      })
      setApplyTarget(null)
      setSelectedRecord(null)
      void fetchCertificationRecords()
    } catch (err) {
      console.error('applyCertification failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleApprove = async (recordId: number) => {
    try {
      await trainingApi.approveCertification(recordId, { comment: undefined })
      void fetchCertificationRecords()
    } catch (err) {
      console.error('approveCertification failed:', err)
    }
  }

  const handleReject = async (recordId: number) => {
    try {
      await trainingApi.rejectCertification(recordId, { comment: undefined })
      void fetchCertificationRecords()
    } catch (err) {
      console.error('rejectCertification failed:', err)
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-medium text-text-primary">认证发证</h2>

      {/* 可申请的认证 */}
      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-2">可申请认证</h3>
        {certifications.length === 0 ? (
          <p className="text-sm text-text-tertiary">暂无认证定义</p>
        ) : (
          <div className="space-y-2">
            {certifications.map((c) => (
              <div key={c.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                <div>
                  <span className="text-sm font-medium text-text-primary">{c.name}</span>
                  <span className="text-xs text-text-tertiary ml-2">{c.code}</span>
                </div>
                <div className="flex items-center gap-3">
                  {c.level && <Badge variant="default">{c.level}</Badge>}
                  <span className="text-xs text-text-tertiary">有效期 {c.validity_period_months} 月</span>
                  <Button variant="secondary" size="sm" onClick={() => setApplyTarget(c)}>申请</Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 认证记录 */}
      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-2">认证记录</h3>
        {certificationRecordsLoading ? (
          <LoadingState />
        ) : certificationRecords.length === 0 ? (
          <p className="text-sm text-text-tertiary">暂无认证记录</p>
        ) : (
          <div className="space-y-2">
            {certificationRecords.map((r) => {
              return (
                <div key={r.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                  <div>
                    <span className="text-sm font-medium text-text-primary">记录 #{r.id}</span>
                    <Badge variant={STATUS_VARIANT[r.status] ?? 'default'} className="ml-2">
                      {STATUS_LABEL[r.status] ?? r.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    {r.certificate_number && (
                      <span className="text-xs text-text-tertiary">证书编号：{r.certificate_number}</span>
                    )}
                    {canReview && r.status === 'pending' && (
                      <>
                        <Button variant="secondary" size="sm" onClick={() => handleApprove(r.id)}>批准</Button>
                        <Button variant="ghost" size="sm" onClick={() => handleReject(r.id)}>拒绝</Button>
                      </>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Card>

      {/* 申请认证 Modal */}
      <Modal
        isOpen={!!applyTarget}
        onClose={() => setApplyTarget(null)}
        maxWidth="max-w-md"
      >
        <div className="p-6">
          <h3 className="text-base font-medium text-text-primary mb-3">申请认证：{applyTarget?.name ?? ''}</h3>
          <div className="space-y-3">
            <p className="text-sm text-text-secondary">选择评估记录作为认证依据：</p>
            {assessmentRecords.filter((r) => r.status === 'completed').map((r) => (
              <div
                key={r.id}
                className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                  selectedRecord?.id === r.id ? 'border-primary bg-primary-light' : 'border-border hover:border-primary'
                }`}
                onClick={() => setSelectedRecord(r)}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm">记录 #{r.id}</span>
                  {r.overall_score != null && <span className="text-sm text-text-secondary">综合分：{r.overall_score}</span>}
                </div>
              </div>
            ))}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setApplyTarget(null)}>取消</Button>
              <Button onClick={handleApply} loading={submitting} disabled={!selectedRecord}>提交申请</Button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
