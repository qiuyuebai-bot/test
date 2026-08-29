import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import GuidanceFeedback from './GuidanceFeedback'
import type { SubmitResult } from './types'

afterEach(() => cleanup())

function buildResult(overrides: Partial<SubmitResult> = {}): SubmitResult {
  return {
    isCorrect: false,
    score: 0,
    agentDecision: { decision: 'simplify', reason: '需要复核关键概念', confidence: 0.8 },
    ...overrides,
  }
}

function renderFeedback(result: SubmitResult) {
  return render(
    <MemoryRouter>
      <GuidanceFeedback questionTopic="梯度下降" result={result} />
    </MemoryRouter>,
  )
}

describe('GuidanceFeedback', () => {
  it('renders knowledge evidence slices from the knowledge base', () => {
    renderFeedback(buildResult({
      generatedContent: {
        simpleExplanation: '讲解正文',
        knowledgeEvidence: [
          { docId: 3, docTitle: '机器学习基础手册', title: '梯度下降优化', contentPreview: '学习率决定每一步沿梯度反方向移动的距离...', similarity: 0.87 },
        ],
      },
    }))

    const panel = screen.getByTestId('guidance-knowledge-evidence')
    expect(within(panel).getByText('内容依据（引用的领域知识库切片）')).toBeInTheDocument()
    expect(within(panel).getByText('机器学习基础手册')).toBeInTheDocument()
    expect(within(panel).getByText('相关度 87%')).toBeInTheDocument()
    expect(within(panel).getByText('梯度下降优化')).toBeInTheDocument()
    expect(within(panel).getByText(/学习率决定每一步/)).toBeInTheDocument()
  })

  it('renders suggested resources with reader links', () => {
    renderFeedback(buildResult({
      generatedContent: {
        simpleExplanation: '讲解正文',
        suggestedResources: [
          { resourceId: 12, title: '梯度下降入门讲义', type: 'lecture', matchScore: 0.92 },
          { resourceId: 15, title: '优化算法练习题', type: 'exercise', matchScore: 88 },
        ],
      },
    }))

    const section = screen.getByTestId('guidance-suggested-resources')
    const links = within(section).getAllByRole('link')
    expect(links).toHaveLength(2)
    expect(links[0]).toHaveAttribute('href', '/resources/12/read')
    expect(links[1]).toHaveAttribute('href', '/resources/15/read')
    expect(within(section).getByText('梯度下降入门讲义')).toBeInTheDocument()
    expect(within(section).getByText('专属讲义 · 匹配度 92%')).toBeInTheDocument()
    expect(within(section).getByText('分阶测试题 · 匹配度 88%')).toBeInTheDocument()
  })

  it('deduplicates resources across content and expansion', () => {
    renderFeedback(buildResult({
      generatedContent: {
        simpleExplanation: '讲解正文',
        suggestedResources: [{ resourceId: 12, title: '梯度下降入门讲义', type: 'lecture' }],
        knowledgeExpansion: {
          overview: '扩展概述',
          suggestedResources: [
            { resourceId: 12, title: '梯度下降入门讲义', type: 'lecture' },
            { resourceId: 20, title: '进阶指南', type: 'guide' },
          ],
        },
      },
    }))

    const section = screen.getByTestId('guidance-suggested-resources')
    expect(within(section).getAllByRole('link')).toHaveLength(2)
  })

  it('hides evidence and resource panels when no data exists', () => {
    renderFeedback(buildResult({
      generatedContent: { simpleExplanation: '讲解正文' },
    }))

    expect(screen.queryByTestId('guidance-knowledge-evidence')).not.toBeInTheDocument()
    expect(screen.queryByTestId('guidance-suggested-resources')).not.toBeInTheDocument()
  })

  it('keeps the decision fallback text', () => {
    renderFeedback(buildResult())

    expect(screen.getByText('判定结果：回答错误 · 通俗纠错')).toBeInTheDocument()
    expect(screen.getByText('需要复核关键概念')).toBeInTheDocument()
  })
})
