import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useShallow } from 'zustand/react/shallow'
import { useStore } from '@/store'
import type { LearnerProfile } from '@/types'
import { PageSkeleton } from '@/components/Skeleton'
import ErrorState from '@/components/ErrorState'
import GuidanceLauncher from '@/features/guidance/GuidanceLauncher'
import GuidanceProcessing from '@/features/guidance/GuidanceProcessing'
import GuidanceQuestion from '@/features/guidance/GuidanceQuestion'
import GuidanceFeedback from '@/features/guidance/GuidanceFeedback'
import GuidanceSessionSummary from '@/features/guidance/GuidanceSessionSummary'
import GuidanceHistoryDrawer from '@/features/guidance/GuidanceHistoryDrawer'
import { useGuidanceSession } from '@/features/guidance/useGuidanceSession'

export default function AdaptiveGuidance() {
  const navigate = useNavigate()
  const {
    currentLearner,
    learners,
    fetchLearners,
    setCurrentLearner,
    learnersLoading,
    learnerError,
    user,
  } = useStore(useShallow((state) => ({
    currentLearner: state.currentLearner,
    learners: state.learners,
    fetchLearners: state.fetchLearners,
    setCurrentLearner: state.setCurrentLearner,
    learnersLoading: state.learnersLoading,
    learnerError: state.learnerError,
    user: state.user,
  })))
  const availableLearners = useMemo(() => {
    const source = currentLearner ? [currentLearner, ...learners] : learners
    return source.filter((learner, index, all) => all.findIndex((candidate) => candidate.id === learner.id) === index)
  }, [currentLearner, learners])
  const [selectedLearnerId, setSelectedLearnerId] = useState<number | null>(null)
  const [launcherDefaults, setLauncherDefaults] = useState({ topic: '', difficulty: '', questionCount: '5' })
  const learner = availableLearners.find((item) => item.id === selectedLearnerId) ?? currentLearner ?? availableLearners[0]
  const session = useGuidanceSession(learner?.id ?? null)

  useEffect(() => {
    if (!selectedLearnerId || !availableLearners.some((item) => item.id === selectedLearnerId)) {
      setSelectedLearnerId(currentLearner?.id ?? availableLearners[0]?.id ?? null)
    }
  }, [availableLearners, currentLearner?.id, selectedLearnerId])

  useEffect(() => {
    if (learner?.id || learners.length > 0 || learnersLoading || learnerError) return
    void fetchLearners({ page: 1, pageSize: 20 })
  }, [fetchLearners, learner?.id, learnerError, learners.length, learnersLoading])

  const handleLearnerChange = (nextLearner: LearnerProfile) => {
    setSelectedLearnerId(nextLearner.id)
    setCurrentLearner(nextLearner)
  }

  const handleStart = (options?: { topic?: string; difficulty?: number; questionCount?: number }) => {
    if (options) {
      setLauncherDefaults((previous) => ({
        topic: options.topic ?? previous.topic,
        difficulty: options.difficulty === undefined ? '' : String(options.difficulty),
        questionCount: options.questionCount === undefined ? previous.questionCount : String(options.questionCount),
      }))
    }
    return session.startSession(options)
  }

  const isLoading = session.state.phase === 'initializing' || (!learner && learnersLoading)
  if (isLoading) return <PageSkeleton type="default" />

  if (learnerError && !learner) {
    return (
      <ErrorState
        type="default"
        title="学习者画像加载失败"
        description="当前账号无法读取学习者画像，请完成画像设置后再继续。"
        details={learnerError}
        onRetry={() => { void fetchLearners({ page: 1, pageSize: 20 }) }}
        onGoHome={() => navigate('/onboarding/name')}
      />
    )
  }

  if (session.state.loadError && learner && !session.question) {
    return (
      <ErrorState
        type="default"
        title="导学题库加载失败"
        description="无法读取当前学习者的导学题目，请稍后重试。"
        details={session.state.loadError}
        onRetry={() => { void session.loadData() }}
      />
    )
  }

  if (!session.question) {
    return (
      <div className="space-y-4 animate-fade-in">
        <GuidanceProcessing phase={session.state.phase} />
        <GuidanceLauncher
          learner={learner}
          learners={availableLearners}
          role={user?.role}
          selectedLearnerId={selectedLearnerId}
          onLearnerChange={handleLearnerChange}
          recommendation={session.recommendation}
          recommendationLoading={session.recommendationLoading}
          recommendationError={session.recommendationError}
          generationError={session.state.generationError}
          loading={session.state.phase === 'generatingQuestion'}
          initialTopic={launcherDefaults.topic}
          initialDifficulty={launcherDefaults.difficulty}
          initialQuestionCount={launcherDefaults.questionCount}
          onStart={handleStart}
          onRefreshRecommendation={() => { void session.loadData() }}
        />
      </div>
    )
  }

  const hasNext = session.state.currentQuestion < session.state.questions.length - 1
  const isSubmitting = session.state.phase === 'submitting'
  return (
    <div className="space-y-4 animate-fade-in">
      <GuidanceSessionSummary
        learner={learner}
        learners={availableLearners}
        role={user?.role}
        selectedLearnerId={selectedLearnerId}
        correctCount={session.state.correctCount}
        answeredCount={session.answeredCount}
        sessionTotal={session.sessionTotal}
        progress={session.progress}
        disabled={isSubmitting || session.isPreparingNext}
        onLearnerChange={handleLearnerChange}
        onExit={session.exitSession}
      />
      <GuidanceProcessing phase={session.state.phase} isPreparingNext={session.isPreparingNext} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <GuidanceQuestion
            question={session.question}
            selectedAnswers={session.state.selectedAnswers}
            showResult={session.state.showResult}
            isSubmitting={isSubmitting}
            isPreparingNext={session.isPreparingNext}
            submitResult={session.state.submitResult}
            answerError={session.state.submissionError}
            nextQuestionError={session.state.nextQuestionError}
            currentGenerationMethod={session.state.generationMethod}
            sessionDifficulty={session.state.sessionConfig?.difficulty}
            questionCount={session.sessionTotal}
            hasNext={hasNext}
            onSelect={session.selectAnswer}
            onSubmit={() => { void session.submitAnswer() }}
            onNext={session.nextQuestion}
            onRetryNext={() => { void session.retryNextQuestion() }}
            onExit={session.exitSession}
          />
          {session.state.showResult && session.state.submitResult && (
            <GuidanceFeedback questionTopic={session.question.topic} result={session.state.submitResult} />
          )}
        </div>
        <GuidanceHistoryDrawer
          learnerName={learner.realName}
          records={session.state.historyRecords}
          loading={session.state.historyLoading}
          error={session.state.historyError}
          onOpen={() => { void session.loadHistory() }}
          onDelete={session.deleteHistory}
          onClear={session.clearHistory}
        />
      </div>
    </div>
  )
}
