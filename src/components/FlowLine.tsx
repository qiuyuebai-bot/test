import { clsx } from 'clsx'

interface FlowLineProps {
  from: { x: number; y: number }
  to: { x: number; y: number }
  type?: 'solid' | 'dashed' | 'animated'
  color?: string
  label?: string
  className?: string
}

export default function FlowLine({
  from,
  to,
  type = 'dashed',
  color = 'var(--color-primary)',
  label,
  className,
}: FlowLineProps) {
  // 计算路径
  const midX = (from.x + to.x) / 2
  const midY = (from.y + to.y) / 2

  const pathD = `M ${from.x} ${from.y} Q ${midX} ${from.y} ${midX} ${midY} T ${to.x} ${to.y}`

  return (
    <g className={clsx('flow-line-container', className)}>
      {/* 底层线 */}
      <path
        d={pathD}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeDasharray={type === 'dashed' ? '8 4' : 'none'}
        className={clsx(
          type === 'animated' && 'animate-[flowDash_1s_linear_infinite]'
        )}
        style={{ strokeDashoffset: 0 }}
      />
      {/* 标签 */}
      {label && (
        <text
          x={midX}
          y={midY - 8}
          textAnchor="middle"
          className="text-xs fill-text-secondary"
        >
          {label}
        </text>
      )}
      {/* 箭头 */}
      <circle
        cx={to.x}
        cy={to.y}
        r={4}
        fill={color}
      />
    </g>
  )
}