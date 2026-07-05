import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithRouter } from '../test/renderPage'

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

beforeEach(() => {
  resetMockStore()
  setMockStore({ currentLearner: sampleLearner })
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
    expect(await screen.findByText('测试学习者')).toBeInTheDocument()
  })
})
