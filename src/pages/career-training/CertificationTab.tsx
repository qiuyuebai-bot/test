import { useEffect, useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import { trainingApi } from '@/api'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Modal from '@/components/Modal'
import { FormField } from '@/components/FormField'
import Input from '@/components/Input'
import Textarea from '@/components/Textarea'
import LoadingState from '@/components/LoadingState'
import type { Certification, AssessmentRecord, CertificationVerification, Position } from '@/types/training'

const STATUS_LABEL: Record<string, string> = {
  pending: '待审核', approved: '已批准', rejected: '已拒绝', expired: '已过期', revoked: '已撤销',
}
const STATUS_VARIANT: Record<string, 'default' | 'info' | 'success' | 'error'> = {
  pending: 'default', approved: 'success', rejected: 'error', expired: 'default', revoked: 'error',
}

export default function CertificationTab() {
  const {
    certifications, certificationRecords, certificationRecordsLoading,
    assessmentRecords, fetchCertifications, fetchCertificationRecords, fetchAssessmentRecords,
    learners, currentLearner, fetchLearners, setCurrentLearner, user,
    positions, fetchPositions,
  } = useStore(
    useShallow((s) => ({
      certifications: s.certifications,
      certificationRecords: s.certificationRecords,
      certificationRecordsLoading: s.certificationRecordsLoading,
      assessmentRecords: s.assessmentRecords,
      fetchCertifications: s.fetchCertifications,
      fetchCertificationRecords: s.fetchCertificationRecords,
      fetchAssessmentRecords: s.fetchAssessmentRecords,
      learners: s.learners,
      currentLearner: s.currentLearner,
      fetchLearners: s.fetchLearners,
      setCurrentLearner: s.setCurrentLearner,
      user: s.user,
      positions: s.positions,
      fetchPositions: s.fetchPositions,
    })),
  )
  const [applyTarget, setApplyTarget] = useState<Certification | null>(null)
  const [selectedRecord, setSelectedRecord] = useState<AssessmentRecord | null>(null)
  const [selectedLearnerId, setSelectedLearnerId] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [verificationResult, setVerificationResult] = useState<CertificationVerification | null>(null)
  const [showCreateCertification, setShowCreateCertification] = useState(false)
  const canReview = user?.role === 'admin' || user?.role === 'teacher'
  const learnerId = canReview ? selectedLearnerId : currentLearner?.id

  useEffect(() => {
    void fetchCertifications()
    void fetchLearners()
    void fetchPositions()
  }, [fetchCertifications, fetchLearners, fetchPositions])

  useEffect(() => {
    void fetchCertificationRecords(canReview && learnerId ? { learnerId } : undefined)
    if (!canReview || learnerId) {
      void fetchAssessmentRecords(learnerId ? { learnerId } : undefined)
    }
  }, [canReview, learnerId, fetchCertificationRecords, fetchAssessmentRecords])

  const eligibleAssessmentRecords = assessmentRecords.filter((record) => {
    const recordLearnerId = record.learner_id ?? record.learnerId
    const recordPositionId = record.position_id ?? record.positionId
    return record.status === 'completed'
      && recordLearnerId === learnerId
      && recordPositionId === (applyTarget?.position_id ?? applyTarget?.positionId)
  })

  const handleApply = async () => {
    if (!applyTarget || !selectedRecord || !learnerId) return
    setSubmitting(true)
    try {
      await trainingApi.applyCertification({
        certification_id: applyTarget.id,
        assessment_record_id: selectedRecord.id,
        learner_id: learnerId,
      })
      setApplyTarget(null)
      setSelectedRecord(null)
      void fetchCertificationRecords(canReview ? { learnerId: learnerId ?? undefined } : undefined)
    } catch (err) {
      console.error('applyCertification failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const handleApprove = async (recordId: number) => {
    try {
      await trainingApi.approveCertification(recordId, { comment: undefined })
      void fetchCertificationRecords(canReview && learnerId ? { learnerId } : undefined)
    } catch (err) {
      console.error('approveCertification failed:', err)
    }
  }

  const handleReject = async (recordId: number) => {
    try {
      await trainingApi.rejectCertification(recordId, { comment: undefined })
      void fetchCertificationRecords(canReview && learnerId ? { learnerId } : undefined)
    } catch (err) {
      console.error('rejectCertification failed:', err)
    }
  }

  const handleRevoke = async (recordId: number) => {
    try {
      await trainingApi.revokeCertification(recordId, { comment: '管理员撤销证书' })
      void fetchCertificationRecords(canReview && learnerId ? { learnerId } : undefined)
    } catch (err) {
      console.error('revokeCertification failed:', err)
    }
  }

  const handleVerify = async (certificateNumber: string) => {
    try {
      const result = await trainingApi.verifyCertification(certificateNumber)
      setVerificationResult(result)
    } catch (err) {
      console.error('verifyCertification failed:', err)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium text-text-primary">认证发证</h2>
        {canReview && (
          <Button size="sm" onClick={() => setShowCreateCertification(true)}>新增认证定义</Button>
        )}
      </div>

      {canReview && (
        <Card>
          <h3 className="text-sm font-medium text-text-primary mb-2">步骤 1：选择学习者</h3>
          <select
            aria-label="认证学习者"
            value={learnerId ?? ''}
            onChange={(event) => {
              const learner = learners.find((item) => item.id === Number(event.target.value))
              setSelectedLearnerId(learner?.id ?? null)
              setCurrentLearner(learner ?? null)
              setApplyTarget(null)
              setSelectedRecord(null)
            }}
            className="w-full max-w-md h-10 px-3 bg-bg-secondary border border-border rounded-input text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary"
          >
            <option value="">请选择学习者</option>
            {learners.map((learner) => (
              <option key={learner.id} value={learner.id}>
                {learner.realName}（#{learner.id}）
              </option>
            ))}
          </select>
          {!learnerId && (
            <p className="text-xs text-text-tertiary mt-2">选择学习者后，才能为该学习者提交认证申请。</p>
          )}
        </Card>
      )}

      {/* 可申请的认证 */}
      <Card>
        <h3 className="text-sm font-medium text-text-primary mb-2">步骤 {canReview ? '2' : '1'}：可申请认证</h3>
        {certifications.length === 0 ? (
          <p className="text-sm text-text-tertiary">暂无认证定义</p>
        ) : (
          <div className="space-y-2">
            {certifications.filter((certification) => certification.is_active ?? certification.isActive).map((c) => (
              <div key={c.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                <div>
                  <span className="text-sm font-medium text-text-primary">{c.name}</span>
                  <span className="text-xs text-text-tertiary ml-2">{c.code}</span>
                </div>
                <div className="flex items-center gap-3">
                  {c.level && <Badge variant="default">{c.level}</Badge>}
                  <span className="text-xs text-text-tertiary">有效期 {c.validity_period_months ?? c.validityPeriodMonths} 月</span>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setApplyTarget(c)
                      setSelectedRecord(null)
                    }}
                    disabled={!learnerId}
                  >
                    申请
                  </Button>
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
              const certificationId = r.certification_id ?? r.certificationId
              const certificateNumber = r.certificate_number ?? r.certificateNumber
              const cert = certifications.find((c) => c.id === certificationId)
              return (
                <div key={r.id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
                  <div>
                    <span className="text-sm font-medium text-text-primary">{cert?.name ?? `认证#${certificationId}`}</span>
                    <Badge variant={STATUS_VARIANT[r.status] ?? 'default'} className="ml-2">
                      {STATUS_LABEL[r.status] ?? r.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    {certificateNumber && (
                      <>
                        <span className="text-xs text-text-tertiary">证书编号：{certificateNumber}</span>
                        <Button aria-label="verify-certificate" variant="ghost" size="sm" onClick={() => handleVerify(certificateNumber)}>验真</Button>
                      </>
                    )}
                    {canReview && (r.learner_id ?? r.learnerId) != null && (
                      <span className="text-xs text-text-tertiary">学习者 #{r.learner_id ?? r.learnerId}</span>
                    )}
                    {canReview && r.status === 'pending' && (
                      <>
                        <Button variant="secondary" size="sm" onClick={() => handleApprove(r.id)}>批准</Button>
                        <Button variant="ghost" size="sm" onClick={() => handleReject(r.id)}>拒绝</Button>
                      </>
                    )}
                    {canReview && r.status === 'approved' && (
                      <Button aria-label="revoke-certificate" variant="ghost" size="sm" onClick={() => handleRevoke(r.id)}>撤销</Button>
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
            {eligibleAssessmentRecords.length === 0 ? (
              <p className="text-sm text-text-tertiary">暂无符合岗位和学员条件的已完成评估</p>
            ) : eligibleAssessmentRecords.map((r) => (
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
              <Button onClick={handleApply} loading={submitting} disabled={!selectedRecord || !learnerId}>提交申请</Button>
            </div>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={!!verificationResult}
        onClose={() => setVerificationResult(null)}
        maxWidth="max-w-md"
      >
        {verificationResult && (
          <div className="p-6 space-y-3">
            <h3 aria-label="certificate-verification-result" className="text-base font-medium text-text-primary">证书验真结果</h3>
            <Badge variant={(verificationResult.is_valid ?? verificationResult.isValid) ? 'success' : 'error'}>
              {(verificationResult.is_valid ?? verificationResult.isValid) ? '证书有效' : '证书无效'}
            </Badge>
            <div className="text-sm text-text-secondary space-y-1">
              <p>证书编号：{verificationResult.certificate_number ?? verificationResult.certificateNumber}</p>
              <p>认证名称：{verificationResult.certification_name ?? verificationResult.certificationName ?? '-'}</p>
              <p>学习者：{verificationResult.learner_name ?? verificationResult.learnerName ?? '-'}</p>
              <p>发证时间：{verificationResult.issued_at ?? verificationResult.issuedAt ?? '-'}</p>
              <p>到期时间：{verificationResult.expires_at ?? verificationResult.expiresAt ?? '永久有效'}</p>
            </div>
            <div className="flex justify-end pt-2">
              <Button aria-label="close-verification" variant="ghost" onClick={() => setVerificationResult(null)}>关闭</Button>
            </div>
          </div>
        )}
      </Modal>

      {canReview && showCreateCertification && (
        <CreateCertificationModal
          positions={positions}
          onClose={() => setShowCreateCertification(false)}
          onCreated={() => {
            setShowCreateCertification(false)
            void fetchCertifications()
          }}
        />
      )}
    </div>
  )
}

function CreateCertificationModal({ positions, onClose, onCreated }: {
  positions: Position[]
  onClose: () => void
  onCreated: () => void
}) {
  const [form, setForm] = useState({
    positionId: '', name: '', code: '', level: 'junior', description: '',
    validityMonths: '0', issuer: '', ruleType: 'overall_score', minScore: '60', allowGap: '0',
  })
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async () => {
    if (!form.positionId || !form.name.trim() || !form.code.trim()) return
    setSubmitting(true)
    try {
      const certification = await trainingApi.createCertification({
        position_id: Number(form.positionId),
        name: form.name.trim(),
        code: form.code.trim(),
        level: form.level,
        description: form.description.trim() || undefined,
        validity_period_months: Number(form.validityMonths) || 0,
        issuer: form.issuer.trim() || undefined,
      })
      await trainingApi.addCertificationRule({
        certification_id: certification.id,
        rule_type: form.ruleType,
        rule_config: form.ruleType === 'overall_score'
          ? { min_score: Number(form.minScore) }
          : { allow_gap: Number(form.allowGap) },
      })
      onCreated()
    } catch (err) {
      console.error('createCertification failed:', err)
    } finally {
      setSubmitting(false)
    }
  }

  const selectClassName = 'w-full h-10 px-3 bg-bg-secondary border border-border rounded-input text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary'

  return (
    <Modal isOpen onClose={onClose} maxWidth="max-w-2xl" className="p-6">
      <h3 className="text-lg font-semibold text-text-primary mb-4 pr-8">新增认证定义</h3>
      <div className="space-y-3">
        <FormField label="关联岗位" required>
          <select aria-label="关联岗位" value={form.positionId} onChange={(event) => setForm({ ...form, positionId: event.target.value })} className={selectClassName}>
            <option value="">请选择岗位</option>
            {positions.map((position) => (
              <option key={position.id} value={position.id}>{position.name} ({position.code})</option>
            ))}
          </select>
        </FormField>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <FormField label="认证名称" required>
            <Input aria-label="认证名称" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          </FormField>
          <FormField label="认证编码" required>
            <Input aria-label="认证编码" value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} placeholder="如：FE-JUNIOR-001" />
          </FormField>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <FormField label="认证级别">
            <select aria-label="认证级别" value={form.level} onChange={(event) => setForm({ ...form, level: event.target.value })} className={selectClassName}>
              <option value="junior">初级</option>
              <option value="mid">中级</option>
              <option value="senior">高级</option>
            </select>
          </FormField>
          <FormField label="有效期（月）" description="0 表示永久有效">
            <Input aria-label="有效期（月）" type="number" min="0" value={form.validityMonths} onChange={(event) => setForm({ ...form, validityMonths: event.target.value })} />
          </FormField>
          <FormField label="发证机构">
            <Input aria-label="发证机构" value={form.issuer} onChange={(event) => setForm({ ...form, issuer: event.target.value })} />
          </FormField>
        </div>
        <FormField label="认证说明">
          <Textarea aria-label="认证说明" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} rows={2} />
        </FormField>
        <div className="border-t border-border pt-3 space-y-3">
          <h4 className="text-sm font-medium text-text-primary">发证规则</h4>
          <FormField label="规则类型" required>
            <select aria-label="规则类型" value={form.ruleType} onChange={(event) => setForm({ ...form, ruleType: event.target.value })} className={selectClassName}>
              <option value="overall_score">综合成绩达标</option>
              <option value="all_mandatory_met">所有必修能力达标</option>
            </select>
          </FormField>
          {form.ruleType === 'overall_score' ? (
            <FormField label="最低综合成绩" required>
              <Input aria-label="最低综合成绩" type="number" min="0" max="100" value={form.minScore} onChange={(event) => setForm({ ...form, minScore: event.target.value })} />
            </FormField>
          ) : (
            <FormField label="允许未达标必修能力数量">
              <Input aria-label="允许未达标必修能力数量" type="number" min="0" value={form.allowGap} onChange={(event) => setForm({ ...form, allowGap: event.target.value })} />
            </FormField>
          )}
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} loading={submitting} disabled={!form.positionId || !form.name.trim() || !form.code.trim() || positions.length === 0}>创建并启用</Button>
        </div>
      </div>
    </Modal>
  )
}
