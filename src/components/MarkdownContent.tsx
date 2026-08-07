import ReactMarkdown, { type Components } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import 'katex/dist/katex.min.css'

interface MarkdownContentProps {
  content: string
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
export default function MarkdownContent({ content }: MarkdownContentProps) {
  return (
    <div className="resource-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={markdownComponents}
        skipHtml
        urlTransform={safeUrl}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
