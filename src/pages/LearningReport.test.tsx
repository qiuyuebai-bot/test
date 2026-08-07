import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithRouter } from '../test/renderPage'
import type { LearnerReport } from '@/types'

vi.mock('@/store', async () => {
  const { useStoreMock } = await import('../test/mockStore')
  return { useStore: useStoreMock }
})
vi.mock('@/hooks', () => ({
  useTaskSSE: () => ({
    events: [], currentStage: null, progress: 0, isConnected: false,
    isCompleted: false, isFailed: false, error: null, lastEvent: null,
  }),
}))
const apiMocks = vi.hoisted(() => ({
  getLearnerReport: vi.fn(),
  getInteractionHistory: vi.fn(),
  getSystemMetrics: vi.fn(),
  getAbilityTrend: vi.fn(),
  downloadLearnerReportPdf: vi.fn(),
}))
vi.mock('@/api', () => ({ coreApi: apiMocks }))
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  RadarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  PolarGrid: () => <div />,
  PolarAngleAxis: () => <div />,
  PolarRadiusAxis: () => <div />,
  Radar: () => <div />,
  AreaChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Area: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
  CartesianGrid: () => <div />,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Line: ({ dataKey }: { dataKey: string }) => <div data-testid={`line-${dataKey}`} />,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => <div />,
}))

const { resetMockStore, setMockStore } = await import('../test/mockStore')

const sampleLearner = {
  id: 1,
  realName: '测试学习者',
  displayName: 'L001',
  educationLevel: 'master',
  major: '计算机科学',
  current_position: '算法工程师',
  learningStyle: 'visual',
  knowledgeStrengths: ['Python'],
  knowledgeBlindAreas: ['分布式训练'],
  theoreticalFoundation: 75,
  programmingAbility: 80,
  algorithmDesign: 70,
  systemArchitecture: 60,
  dataAnalysis: 65,
  engineeringPractice: 72,
}

const sampleReport = {
  success: true,
  learnerId: 1,
  learnerInfo: {
    id: 1,
    name: '后端学习者',
    education: '硕士',
    major: '人工智能',
    learningStyle: 'visual',
    targetIndustry: '人工智能',
    targetPosition: '算法工程师',
  },
  blindAreaHeatmap: {
    labels: ['理论基础'],
    severityLevels: ['high', 'medium', 'low'],
    severityLabels: ['高', '中', '低'],
    data: [{
      dimension: '理论基础',
      dimensionKey: 'theoretical_foundation',
      severity: 'medium',
      severityLabel: '中',
      value: 30,
      score: 58,
      isBlind: true,
      description: '建议加强理论基础',
    }],
  },
  difficultyMatchCurve: {
    labels: ['资源1'],
    difficulty: [4],
    matchScore: [75.5],
    learnerAbility: [68],
    data: [{
      name: '资源1',
      difficulty: 4,
      matchScore: 75.5,
      learnerAbility: 68,
      resourceId: 10,
      title: '测试资源',
    }],
    learnerAbilityRaw: 68,
  },
  learningPathTopology: {
    totalSteps: 2,
    currentStep: 1,
    progress: 50,
    estimatedTotalTime: '6小时',
    nodes: [{
      id: 'step-1',
      name: '路径第一步',
      difficulty: 2,
      status: 'current',
      estimatedTime: '2小时',
      resources: [{ resourceId: 10, title: '测试资源' }],
      description: '建立基础知识',
    }],
    edges: [],
  },
  abilityRadar: {
    dimensions: ['理论基础'],
    data: [{ dimension: '理论基础', score: 58, fullMark: 100 }],
    averageScore: 58,
  },
  coreMetrics: {
    resourceMatchAccuracy: 75.5,
    knowledgeCoverageRate: 82.5,
    answerAccuracy: 68,
  },
  statistics: {
    totalResources: 1,
    totalAnswers: 2,
    avgAnswerScore: 68,
    knowledgeBlindCount: 1,
  },
} satisfies LearnerReport

beforeEach(() => {
  resetMockStore()
  setMockStore({ currentLearner: sampleLearner })
  apiMocks.getLearnerReport.mockReset().mockResolvedValue(sampleReport)
  apiMocks.getInteractionHistory.mockReset().mockResolvedValue({
    learnerId: 1,
    history: [],
    total: 0,
    page: 1,
    pageSize: 20,
  })
  apiMocks.getSystemMetrics.mockReset().mockResolvedValue({ hallucinationRate: 2 })
  apiMocks.getAbilityTrend.mockReset().mockResolvedValue([])
})

describe('LearningReport page', () => {
  it('renders the ability radar chart section', async () => {
    const { default: Page } = await import('./LearningReport')
    renderWithRouter(<Page />)
    expect(await screen.findByText('知识能力雷达图')).toBeInTheDocument()
  })

  it('renders the ability development section', async () => {
    const { default: Page } = await import('./LearningReport')
    renderWithRouter(<Page />)
    expect(await screen.findByText('能力发展趋势')).toBeInTheDocument()
  })

  it('renders the learner name heading', async () => {
    const { default: Page } = await import('./LearningReport')
    renderWithRouter(<Page />)
    expect(await screen.findByText('后端学习者')).toBeInTheDocument()
  })

  it('renders the camelCase report payload instead of empty chart states', async () => {
    const { default: Page } = await import('./LearningReport')
    renderWithRouter(<Page />)

    expect(await screen.findByText('路径第一步')).toBeInTheDocument()
    expect(screen.getByText('82.5%')).toBeInTheDocument()
    expect(screen.getByText('理论基础')).toBeInTheDocument()
    expect(screen.queryByText('暂无热力图数据')).not.toBeInTheDocument()
    expect(screen.getByTestId('line-learnerAbility')).toBeInTheDocument()
    expect(screen.getByTestId('line-matchScore')).toBeInTheDocument()
  })

  it('offers the knowledge upload action when there is no evidence', async () => {
    const { default: Page } = await import('./LearningReport')
    renderWithRouter(<Page />)

    expect(await screen.findByText('No evidence')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Upload relevant materials' })).toBeInTheDocument()
  })

  it('summarizes adaptive answers by round accuracy instead of 100-point scores', async () => {
    apiMocks.getInteractionHistory.mockResolvedValue({
      learnerId: 1,
      history: Array.from({ length: 7 }, (_, index) => ({
        recordId: index + 1,
        sessionId: 'round-accuracy',
        sequenceIndex: index,
        questionId: index + 10,
        questionType: index === 2 || index === 5 ? 'multiple' : 'single',
        questionTopic: 'REST API',
        questionDifficulty: 4,
        userAnswer: ['A'],
        result: index < 3 ? 'correct' : 'wrong',
        score: index < 3 ? 100 : 0,
        timeSpentMs: 1000,
        agentDecision: index < 3 ? 'advance' : 'simplify',
        decisionReason: null,
        decisionConfidence: null,
        nextAction: null,
        nextResourceId: null,
        feedbackGiven: null,
        createdAt: `2026-08-07T10:0${index}:00`,
      })),
      total: 7,
      page: 1,
      pageSize: 100,
    })

    const { default: Page } = await import('./LearningReport')
    renderWithRouter(<Page />)

    expect((await screen.findAllByText('43%')).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('3 / 7')).toBeInTheDocument()
    expect(screen.getByText('1 轮')).toBeInTheDocument()
    expect(screen.queryByText('/ 100')).not.toBeInTheDocument()
  })
})
