import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, HelpCircle, Plus, RotateCcw, Sparkles, Trash2 } from 'lucide-react'
import type { LearnerProfile } from '@/types'
import { diagnosticApi, type DiagnosticSession } from '@/api'
import Button from './Button'
import Modal from './Modal'

type SaveData = Partial<LearnerProfile> & {
  manualAbilityAdjustments?: Record<string, number>
}

interface LearnerProfileWizardProps {
  isOpen: boolean
  onClose: () => void
  learner?: LearnerProfile
  onSave: (data: SaveData, options?: { close?: boolean }) => Promise<LearnerProfile | undefined>
}

const educationOptions = [
  { value: '高中', label: '高中' },
  { value: '大专', label: '大专' },
  { value: '本科', label: '本科' },
  { value: '硕士', label: '硕士' },
  { value: '博士', label: '博士' },
]

const learningStyles = [
  { value: 'visual', label: '视觉型', description: '看图示、流程图或演示后更容易理解' },
  { value: 'auditory', label: '听觉型', description: '听讲解、讨论或复述后更容易记住' },
  { value: 'reading', label: '阅读型', description: '阅读文字、文档或步骤后更容易掌握' },
  { value: 'kinesthetic', label: '动手型', description: '通过操作、实验或练习边做边学' },
  { value: 'uncertain', label: '我不确定', description: '暂时不判断，系统会根据学习过程调整' },
]

const dimensions = [
  { key: 'theoreticalFoundation', label: '理论基础', description: '理解概念、原理和前提条件' },
  { key: 'programmingAbility', label: '编程能力', description: '使用代码实现清晰、可运行的解决方案' },
  { key: 'algorithmDesign', label: '算法设计', description: '拆解问题并选择合适的算法' },
  { key: 'systemArchitecture', label: '系统架构', description: '组织模块、接口和系统边界' },
  { key: 'dataAnalysis', label: '数据分析', description: '读取数据、发现规律并解释结果' },
  { key: 'engineeringPractice', label: '工程实践', description: '测试、调试、交付和维护项目' },
] as const

const dimensionLabels = Object.fromEntries(dimensions.map((item) => [item.key, item.label]))

type FormData = {
  realName: string
  educationLevel: string
  major: string
  learningStyle: string
  knowledgeBlindAreas: string[]
}

function initialFormData(learner?: LearnerProfile): FormData {
  return {
    realName: learner?.realName || '',
    educationLevel: learner?.educationLevel || '本科',
    major: learner?.major || '',
    learningStyle: learner?.learningStyle || 'uncertain',
    knowledgeBlindAreas: learner?.knowledgeBlindAreas || [],
  }
}

function currentScore(learner: LearnerProfile | undefined, key: keyof LearnerProfile): number {
  const score = learner?.[key]
  return typeof score === 'number' ? score : 0
}

function questionAnswer(selected: number[]): string[] {
  return selected.map((index) => String.fromCharCode(65 + index))
}

export default function LearnerProfileWizard({ isOpen, onClose, learner, onSave }: LearnerProfileWizardProps) {
  const [step, setStep] = useState(0)
  const [formData, setFormData] = useState<FormData>(() => initialFormData(learner))
  const [activeLearner, setActiveLearner] = useState<LearnerProfile | undefined>(learner)
  const [session, setSession] = useState<DiagnosticSession | null>(null)
  const [selectedAnswers, setSelectedAnswers] = useState<number[]>([])
  const [questionsPerDimension, setQuestionsPerDimension] = useState<2 | 3>(2)
  const [manualAdjustments, setManualAdjustments] = useState<Record<string, number>>({})
  const [newBlindArea, setNewBlindArea] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setStep(0)
    setFormData(initialFormData(learner))
    setActiveLearner(learner)
    setSession(null)
    setSelectedAnswers([])
    setQuestionsPerDimension(2)
    setManualAdjustments({})
    setNewBlindArea('')
    setError(null)
  }, [isOpen, learner?.id])

  const currentQuestion = useMemo(
    () => session?.questions.find((question) => !question.answered) ?? null,
    [session],
  )

  const baseSaveData = (): SaveData => ({
    realName: formData.realName.trim(),
    educationLevel: formData.educationLevel,
    major: formData.major.trim(),
    learningStyle: formData.learningStyle,
    knowledgeBlindAreas: formData.knowledgeBlindAreas,
    theoreticalFoundation: currentScore(activeLearner, 'theoreticalFoundation'),
    programmingAbility: currentScore(activeLearner, 'programmingAbility'),
    algorithmDesign: currentScore(activeLearner, 'algorithmDesign'),
    systemArchitecture: currentScore(activeLearner, 'systemArchitecture'),
    dataAnalysis: currentScore(activeLearner, 'dataAnalysis'),
    engineeringPractice: currentScore(activeLearner, 'engineeringPractice'),
  })

  const validateBasics = () => {
    if (!formData.realName.trim()) {
      setError('请先填写姓名')
      return false
    }
    if (!formData.major.trim()) {
      setError('请先填写专业或学习方向')
      return false
    }
    return true
  }

  const startDiagnostic = async () => {
    if (!validateBasics()) return
    setLoading(true)
    setError(null)
    try {
      let profile = activeLearner
      profile = await onSave(baseSaveData(), { close: false }) || profile
      if (!profile) throw new Error('画像保存后才能开始诊断')
      setActiveLearner(profile)
      const nextSession = await diagnosticApi.createSession(profile.id, questionsPerDimension)
      setSession(nextSession)
      setSelectedAnswers([])
      setStep(nextSession.status === 'completed' ? 3 : 2)
    } catch (err) {
      setError(err instanceof Error ? err.message : '诊断准备失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  const selectAnswer = (index: number) => {
    if (!currentQuestion || currentQuestion.answered) return
    if (currentQuestion.type === 'multiple') {
      setSelectedAnswers((previous) => previous.includes(index)
        ? previous.filter((item) => item !== index)
        : [...previous, index].sort((a, b) => a - b))
    } else {
      setSelectedAnswers([index])
    }
  }

  const submitAnswer = async () => {
    if (!session || !currentQuestion || selectedAnswers.length === 0) {
      setError('请选择答案后继续')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const result = await diagnosticApi.submitAnswer(session.sessionId, {
        questionId: currentQuestion.id,
        userAnswer: questionAnswer(selectedAnswers),
      })
      const questions = session.questions.map((question) => (
        question.id === currentQuestion.id ? { ...question, answered: true } : question
      ))
      const nextSession: DiagnosticSession = {
        ...session,
        questions,
        answeredQuestions: questions.filter((question) => question.answered).length,
        status: result.sessionComplete ? 'completed' : session.status,
        assessments: result.assessments || session.assessments,
      }
      setSession(nextSession)
      setSelectedAnswers([])
      if (result.sessionComplete || !questions.some((question) => !question.answered)) {
        setStep(3)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '答案提交失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  const addBlindArea = () => {
    const value = newBlindArea.trim()
    if (!value || formData.knowledgeBlindAreas.includes(value)) return
    setFormData((previous) => ({ ...previous, knowledgeBlindAreas: [...previous.knowledgeBlindAreas, value] }))
    setNewBlindArea('')
  }

  const finish = async () => {
    setLoading(true)
    setError(null)
    try {
      const adjustments = Object.fromEntries(
        Object.entries(manualAdjustments).filter(([, value]) => Number.isFinite(value) && value !== 0),
      )
      await onSave({ ...baseSaveData(), manualAbilityAdjustments: adjustments })
    } catch (err) {
      setError(err instanceof Error ? err.message : '画像保存失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  const progress = step === 2 && session ? `${session.answeredQuestions}/${session.totalQuestions}` : `${step + 1}/5`

  return (
    <Modal isOpen={isOpen} onClose={onClose} maxWidth="max-w-2xl" className="max-h-[92vh] overflow-y-auto p-7">
      <div className="pr-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-primary">学习者画像 · {progress}</p>
            <h2 className="mt-1 text-xl font-semibold text-text-primary">
              {step === 0 ? '先建立基本背景' : step === 1 ? '选择更适合你的学习方式' : step === 2 ? '完成六维能力诊断' : step === 3 ? '查看系统估算结果' : '补充知识盲区'}
            </h2>
          </div>
          <Sparkles className="h-5 w-5 text-primary" aria-hidden="true" />
        </div>

        <div className="mt-5 flex gap-1" aria-label="画像设置进度">
          {[0, 1, 2, 3, 4].map((item) => (
            <div key={item} className={`h-1.5 flex-1 rounded-full ${item <= step ? 'bg-primary' : 'bg-bg-tertiary'}`} />
          ))}
        </div>

        {error && <p role="alert" className="mt-4 rounded-lg border border-error/20 bg-error-light px-3 py-2 text-sm text-error">{error}</p>}

        {step === 0 && (
          <div className="mt-6 space-y-4">
            <label className="block text-sm font-medium text-text-primary">
              姓名
              <input value={formData.realName} onChange={(event) => setFormData({ ...formData, realName: event.target.value })} className="mt-1.5 h-10 w-full rounded-lg border border-border bg-bg-secondary px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" />
            </label>
            <label className="block text-sm font-medium text-text-primary">
              学历
              <select value={formData.educationLevel} onChange={(event) => setFormData({ ...formData, educationLevel: event.target.value })} className="mt-1.5 h-10 w-full rounded-lg border border-border bg-bg-secondary px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20">
                {educationOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select>
            </label>
            <label className="block text-sm font-medium text-text-primary">
              专业或学习方向
              <input value={formData.major} onChange={(event) => setFormData({ ...formData, major: event.target.value })} className="mt-1.5 h-10 w-full rounded-lg border border-border bg-bg-secondary px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" placeholder="例如：计算机科学、产品设计" />
            </label>
          </div>
        )}

        {step === 1 && (
          <div className="mt-6 space-y-3">
            <p className="text-sm text-text-secondary">选择最接近你平时学习习惯的一项；这不是能力测试，也可以暂时不判断。</p>
            {learningStyles.map((style) => (
              <button key={style.value} type="button" onClick={() => setFormData({ ...formData, learningStyle: style.value })} className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left transition-colors ${formData.learningStyle === style.value ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/40'}`}>
                <span className={`mt-0.5 h-4 w-4 rounded-full border-2 ${formData.learningStyle === style.value ? 'border-primary bg-primary ring-2 ring-primary/20' : 'border-border'}`} aria-hidden="true" />
                <span><span className="block text-sm font-medium text-text-primary">{style.label}</span><span className="mt-0.5 block text-xs text-text-secondary">{style.description}</span></span>
              </button>
            ))}
            <div className="border-t border-border pt-4">
              <p className="text-sm font-medium text-text-primary">诊断题量</p>
              <p className="mt-1 text-xs text-text-secondary">每个能力维度回答 2 或 3 题，系统会据此估算初始分数。</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {([2, 3] as const).map((count) => (
                  <button
                    key={count}
                    type="button"
                    onClick={() => setQuestionsPerDimension(count)}
                    className={`rounded-xl border p-3 text-left transition-colors ${questionsPerDimension === count ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/40'}`}
                  >
                    <span className="block text-sm font-medium text-text-primary">每维 {count} 题</span>
                    <span className="mt-0.5 block text-xs text-text-secondary">共 {count * dimensions.length} 题，约 {count * dimensions.length * 1} 分钟</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {step === 2 && currentQuestion && (
          <div className="mt-6">
            <div className="mb-4 flex items-center justify-between text-xs text-text-secondary">
              <span>{dimensionLabels[currentQuestion.abilityDimension || ''] || '能力维度'}</span>
              <span>每个维度 {session?.questionsPerDimension ?? questionsPerDimension} 题 · 可随时关闭后恢复</span>
            </div>
            <h3 className="text-base font-medium leading-relaxed text-text-primary">{currentQuestion.question}</h3>
            <div className="mt-5 space-y-2">
              {currentQuestion.options.map((option, index) => {
                const selected = selectedAnswers.includes(index)
                return <button key={`${currentQuestion.id}-${index}`} type="button" onClick={() => selectAnswer(index)} className={`flex w-full items-start gap-3 rounded-xl border p-3 text-left text-sm transition-colors ${selected ? 'border-primary bg-primary/5 text-primary' : 'border-border text-text-primary hover:border-primary/40'}`}><span className="flex h-6 w-6 flex-none items-center justify-center rounded-full border text-xs font-semibold">{String.fromCharCode(65 + index)}</span><span>{option}</span></button>
              })}
            </div>
            <div className="mt-6 flex items-center justify-between">
              <span className="flex items-center gap-1 text-xs text-text-tertiary"><HelpCircle className="h-3.5 w-3.5" />每题只记录一次答案</span>
              <Button variant="primary" loading={loading} disabled={selectedAnswers.length === 0} onClick={() => { void submitAnswer() }}>提交答案 <ArrowRight className="h-4 w-4" /></Button>
            </div>
          </div>
        )}

        {step === 2 && !currentQuestion && session && (
          <div className="mt-10 text-center"><Check className="mx-auto h-10 w-10 text-success" /><p className="mt-3 text-sm text-text-secondary">诊断已完成，正在整理六维结果。</p><Button className="mt-5" onClick={() => setStep(3)}>查看结果</Button></div>
        )}

        {step === 3 && session && (
          <div className="mt-6 space-y-3">
            <p className="text-sm text-text-secondary">分数来自每个维度 {session.questionsPerDimension} 道诊断题。置信度表示当前证据量，不代表永久能力。</p>
            {dimensions.map((dimension) => {
              const assessment = session.assessments[dimension.key]
              const score = assessment?.estimatedScore
              return <div key={dimension.key} className="rounded-xl border border-border p-3"><div className="flex items-center justify-between"><div><p className="text-sm font-medium text-text-primary">{dimension.label}</p><p className="text-xs text-text-secondary">{assessment?.answeredCount || 0} 题 · 置信度 {Math.round((assessment?.confidence || 0) * 100)}%</p></div><span className="text-lg font-semibold text-primary">{score === null || score === undefined ? '待评估' : score}</span></div><div className="mt-2 flex items-center gap-3"><div className="h-2 flex-1 overflow-hidden rounded-full bg-bg-tertiary"><div className="h-full rounded-full bg-primary" style={{ width: `${score || 0}%` }} /></div><input aria-label={`${dimension.label}手动修正`} type="number" min={-50} max={50} value={manualAdjustments[dimension.key] ?? 0} onChange={(event) => setManualAdjustments({ ...manualAdjustments, [dimension.key]: Number(event.target.value) })} className="h-8 w-20 rounded border border-border bg-bg-secondary px-2 text-right text-xs" /></div><p className="mt-1 text-right text-[11px] text-text-tertiary">手动修正（-50 到 +50，可选）</p></div>
            })}
          </div>
        )}

        {step === 4 && (
          <div className="mt-6">
            <p className="text-sm text-text-secondary">写下你想补强的主题，系统会将它们作为后续推荐线索；这一步可以跳过。</p>
            <div className="mt-4 flex gap-2"><input value={newBlindArea} onChange={(event) => setNewBlindArea(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); addBlindArea() } }} className="h-10 flex-1 rounded-lg border border-border bg-bg-secondary px-3 text-sm outline-none focus:border-primary" placeholder="例如：分布式训练" /><Button variant="outline" onClick={addBlindArea}><Plus className="h-4 w-4" />添加</Button></div>
            <div className="mt-4 flex flex-wrap gap-2">{formData.knowledgeBlindAreas.map((area) => <span key={area} className="inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/5 px-3 py-1.5 text-xs text-primary">{area}<button type="button" aria-label={`删除${area}`} onClick={() => setFormData({ ...formData, knowledgeBlindAreas: formData.knowledgeBlindAreas.filter((item) => item !== area) })}><Trash2 className="h-3 w-3" /></button></span>)}</div>
          </div>
        )}

        <div className="mt-7 flex items-center justify-between border-t border-border pt-5">
          {step > 0 && step !== 2 ? <Button variant="ghost" disabled={loading} onClick={() => setStep(step - 1)}><ArrowLeft className="h-4 w-4" />上一步</Button> : <span />}
          {step === 0 && <Button onClick={() => { if (validateBasics()) setStep(1) }}>下一步 <ArrowRight className="h-4 w-4" /></Button>}
          {step === 1 && <Button loading={loading} onClick={() => { void startDiagnostic() }}>{session ? '继续诊断' : `开始 ${questionsPerDimension * dimensions.length} 题诊断`} <ArrowRight className="h-4 w-4" /></Button>}
          {step === 3 && <div className="flex gap-2"><Button variant="outline" disabled={loading} onClick={() => { setSession(null); setStep(1) }}><RotateCcw className="h-4 w-4" />重新诊断</Button><Button onClick={() => setStep(4)}>下一步 <ArrowRight className="h-4 w-4" /></Button></div>}
          {step === 4 && <Button loading={loading} onClick={() => { void finish() }}><Check className="h-4 w-4" />保存画像</Button>}
        </div>
      </div>
    </Modal>
  )
}
