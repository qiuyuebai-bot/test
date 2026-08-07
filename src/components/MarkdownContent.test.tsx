import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import MarkdownContent from './MarkdownContent'

describe('MarkdownContent', () => {
  it('renders generated learning-content Markdown, including tables and formulas', () => {
    const { container } = render(
      <MarkdownContent
        content={
          '# 反向传播算法\n\n**学习目标**\n\n1. 理解链式法则\n\n| 阶段 | 目标 |\n| --- | --- |\n| 一 | 掌握基础 |\n\n公式：$E = mc^2$\n\n[参考资料](https://example.com)'
        }
      />,
    )

    expect(screen.getByRole('heading', { name: '反向传播算法' })).toBeInTheDocument()
    expect(container.querySelector('strong')).toHaveTextContent('学习目标')
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(container.querySelector('.katex')).toBeInTheDocument()

    const link = screen.getByRole('link', { name: '参考资料' })
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('does not render raw HTML, unsafe links, or remote images', () => {
    const { container } = render(
      <MarkdownContent
        content={
          '<script>window.alert(1)</script>\n\n[不安全链接](javascript:alert(1))\n\n![远程图片](https://example.com/image.png)'
        }
      />,
    )

    expect(container.querySelector('script')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '不安全链接' })).not.toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
