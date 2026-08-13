import { useState } from 'react'
import { useShallow } from 'zustand/react/shallow'
import { useGuidanceSession } from '@/features/guidance/useGuidanceSession'
import { useStore } from '@/store'
import Card from '@/components/Card'
import Badge from '@/components/Badge'
import Button from '@/components/Button'
import Input from '@/components/Input'
import LoadingState from '@/components/LoadingState'
import EmptyState from '@/components/EmptyState'
import type { PositionDetail } from '@/types/training'

interface Props {
  position: PositionDetail | null
  learnerId: number | null
}

export default function EmbeddedAdaptivePractice({ position, learnerId }: Props) {
  const trainingContext = useStore(useShallow((state) => state.activeTrainingContext))
  const session = useGuidanceSession(learnerId, trainingContext)
  const { state, question, sessionTotal, answeredCount, isPreparingNext } = session
  const [customTopic, setCustomTopic] = useState('')
  const [difficulty, setDifficulty] = useState('')
  const [questionCount, setQuestionCount] = useState('5')

  if (!learnerId) {
    return <EmptyState type="default" title="需要学习者画像" description="当前账号没有关联的学习者画像，无法开始练习" />
  }

  const defaultTopic = trainingContext?.stage.title ?? position?.name ?? ''
  const handleStart = () => {
    void session.startSession({
      topic: customTopic.trim() || defaultTopic,
      difficulty: difficulty ? Number(difficulty) : undefined,
      questionCount: Number(questionCount) || 5,
    })
  }

  const isReady = state.phase === 'ready' || state.phase === 'initializing'
  const isAnswering = state.phase === 'answering' || state.phase === 'submitting'
  const isFeedback = state.phase === 'feedback'
  const isCompleted = state.phase === 'completed'

  return (
    <div className="space-y-4">
      {/* 岗位上下文条 */}
      {position && (
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <Badge variant="info">{position.name}</Badge>
          {position.industry && <span>· {position.industry}</span>}
          {state.sessionConfig?.topic && (
            <span>· 主题：{state.sessionConfig.topic}</span>
          )}
          {trainingContext?.stage.targetLevel && <span>· 目标 L{trainingContext.stage.targetLevel}</span>}
        </div>
      )}

      {/* 就绪 / 配置阶段 */}
      {isReady && (
        <Card>
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-text-primary mb-1">练习配置</h3>
              <p className="text-xs text-text-tertiary">主题默认使用当前培训阶段，可自由修改</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1">主题</label>
                <Input
                  value={customTopic}
                  onChange={(e) => setCustomTopic(e.target.value)}
                  placeholder={defaultTopic || '输入练习主题'}
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1">难度（留空=动态）</label>
                <Input
                  type="number"
                  min={1} max={5}
                  value={difficulty}
                  onChange={(e) => setDifficulty(e.target.value)}
                  placeholder="1-5"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1">题量</label>
                <Input
                  type="number"
                  min={1} max={10}
                  value={questionCount}
                  onChange={(e) => setQuestionCount(e.target.value)}
                />
              </div>
            </div>
            <div className="flex justify-end">
              <Button onClick={handleStart} loading={state.phase === 'initializing'}>
                开始练习
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* 生成中 */}
      {state.phase === 'generatingQuestion' && (
        <Card><LoadingState /></Card>
      )}

      {/* 答题阶段 */}
      {isAnswering && question && (
        <Card>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Badge variant="info">{question.type === 'multiple' ? '多选' : '单选'}</Badge>
              <span className="text-xs text-text-tertiary">难度 L{question.difficulty} · {answeredCount + 1}/{sessionTotal}</span>
            </div>
            <div className="text-sm font-medium text-text-primary whitespace-pre-wrap">{question.question}</div>
            <div className="space-y-2">
              {question.options.map((opt: string, idx: number) => {
                const selected = state.selectedAnswers.includes(idx)
                return (
                  <button
                    key={idx}
                    onClick={() => session.selectAnswer(idx)}
                    className={`w-full text-left px-3 py-2 rounded-lg border text-sm transition-colors ${
                      selected ? 'border-primary bg-primary-light text-primary' : 'border-border hover:border-primary'
                    }`}
                  >
                    <span className="font-medium mr-2">{String.fromCharCode(65 + idx)}.</span>
                    {opt}
                  </button>
                )
              })}
            </div>
            <div className="flex justify-end gap-2">
              <Button
                onClick={() => void session.submitAnswer()}
                disabled={state.selectedAnswers.length === 0 || state.phase === 'submitting'}
                loading={state.phase === 'submitting'}
              >
                提交答案
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* 反馈阶段 */}
      {isFeedback && state.submitResult && (
        <Card>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Badge variant={state.submitResult.isCorrect ? 'success' : 'error'}>
                {state.submitResult.isCorrect ? '回答正确' : '回答错误'}
              </Badge>
              <span className="text-sm text-text-secondary">得分：{state.submitResult.score}</span>
            </div>
            {state.submitResult.agentDecision?.reason && (
              <div className="p-3 bg-bg-secondary rounded-lg text-sm text-text-secondary">
                {state.submitResult.agentDecision.reason}
              </div>
            )}
            {state.submitResult.generatedContent?.simpleExplanation && (
              <div className="text-sm text-text-primary whitespace-pre-wrap">
                {state.submitResult.generatedContent.simpleExplanation}
              </div>
            )}
            <div className="flex justify-end gap-2">
              {answeredCount < sessionTotal ? (
                <Button onClick={() => {
                  session.nextQuestion()
                  if (isPreparingNext) void session.retryNextQuestion()
                }}>
                  下一题
                </Button>
              ) : (
                <Button onClick={() => session.exitSession()}>完成本轮</Button>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* 完成阶段 */}
      {isCompleted && (
        <Card>
          <div className="text-center py-6 space-y-3">
            <div className="text-lg font-medium text-text-primary">本轮练习完成</div>
            <div className="text-sm text-text-secondary">
              正确 {state.correctCount} / {sessionTotal} · 正确率 {sessionTotal > 0 ? Math.round(state.correctCount / sessionTotal * 100) : 0}%
            </div>
            <Button variant="secondary" onClick={() => session.exitSession()}>重新配置</Button>
          </div>
        </Card>
      )}

      {/* 历史记录摘要 */}
      {state.historyRecords.length > 0 && (
        <Card>
          <h3 className="text-sm font-medium text-text-primary mb-2">近期答题</h3>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {state.historyRecords.slice(0, 10).map((r) => (
              <div key={r.recordId} className="flex items-center justify-between py-1.5 border-b border-border last:border-0 text-xs">
                <span className="text-text-secondary truncate">{r.questionTopic}</span>
                <Badge variant={r.result === 'correct' ? 'success' : 'error'} className="ml-2">
                  {r.result === 'correct' ? '对' : '错'}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* 错误提示 */}
      {state.generationError && (
        <div className="p-3 bg-error-light rounded-lg text-sm text-error-dark">{state.generationError}</div>
      )}
      {state.submissionError && (
        <div className="p-3 bg-error-light rounded-lg text-sm text-error-dark">{state.submissionError}</div>
      )}
    </div>
  )
}
