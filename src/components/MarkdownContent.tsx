import ReactMarkdown, { type Components } from 'react-markdown'
import type { ReactNode } from 'react'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import 'katex/dist/katex.min.css'

interface MarkdownContentProps {
  content: string
  headingIdPrefix?: string
}

function safeUrl(url: string): string {
  const normalizedUrl = url.trim()
  return /^(https?:\/\/|mailto:|#)/i.test(normalizedUrl) ? normalizedUrl : ''
}

const markdownComponents: Components = {
  a: ({ children, href }) => {
    const sanitizedHref = href ? safeUrl(href) : ''
    if (!sanitizedHref) return <span>{children}</span>

    const isExternal = /^https?:\/\//i.test(sanitizedHref)
    return (
      <a
        href={sanitizedHref}
        target={isExternal ? '_blank' : undefined}
        rel={isExternal ? 'noopener noreferrer' : undefined}
      >
        {children}
      </a>
    )
  },
  img: () => null,
  table: ({ children }) => (
    <div className="resource-markdown-table">
      <table>{children}</table>
    </div>
  ),
}

/** Safely renders Markdown generated for the resource-generation page. */
function headingText(children: ReactNode): string {
  if (typeof children === 'string' || typeof children === 'number') return String(children)
  if (Array.isArray(children)) return children.map((child) => headingText(child)).join('')
  return ''
}

function headingSlug(text: string, index: number, prefix: string): string {
  const slug = text.toLowerCase().replace(/[^\w\u4e00-\u9fff]+/g, '-').replace(/^-|-$/g, '')
  return `${prefix}-${slug || 'section'}-${index}`
}

export default function MarkdownContent({ content, headingIdPrefix }: MarkdownContentProps) {
  let headingIndex = 0
  const components: Components = headingIdPrefix ? {
    ...markdownComponents,
    h1: ({ children }) => <h1 id={headingSlug(headingText(children), headingIndex++, headingIdPrefix)}>{children}</h1>,
    h2: ({ children }) => <h2 id={headingSlug(headingText(children), headingIndex++, headingIdPrefix)}>{children}</h2>,
    h3: ({ children }) => <h3 id={headingSlug(headingText(children), headingIndex++, headingIdPrefix)}>{children}</h3>,
  } : markdownComponents
  return (
    <div className="resource-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={components}
        skipHtml
        urlTransform={safeUrl}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
