import { useMemo } from 'react'

export interface RadarItem {
  name: string
  current?: number
  required: number
}

interface Props {
  items: RadarItem[]
  size?: number
}

const LEVEL_MAX = 5

export default function CompetencyRadar({ items, size = 320 }: Props) {
  const center = size / 2
  const radius = size / 2 - 50

  const points = useMemo(() => {
    if (items.length < 3) return null
    const n = items.length
    const angleStep = (2 * Math.PI) / n
    return items.map((item, i) => {
      const angle = i * angleStep - Math.PI / 2
      const requiredR = (item.required / LEVEL_MAX) * radius
      const currentR = ((item.current ?? 0) / LEVEL_MAX) * radius
      return {
        name: item.name,
        labelX: center + Math.cos(angle) * (radius + 20),
        labelY: center + Math.sin(angle) * (radius + 20),
        requiredX: center + Math.cos(angle) * requiredR,
        requiredY: center + Math.sin(angle) * requiredR,
        currentX: center + Math.cos(angle) * currentR,
        currentY: center + Math.sin(angle) * currentR,
        angle,
      }
    })
  }, [items, center, radius])

  if (!items.length) {
    return (
      <div className="flex items-center justify-center h-48 text-text-tertiary text-sm">
        暂无胜任力数据
      </div>
    )
  }

  if (!points) {
    return (
      <div className="flex items-center justify-center h-48 text-text-tertiary text-sm">
        胜任力项不足 3 个，无法绘制雷达图
      </div>
    )
  }

  const requiredPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.requiredX} ${p.requiredY}`).join(' ') + ' Z'
  const currentPath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.currentX} ${p.currentY}`).join(' ') + ' Z'

  return (
    <svg
      role="img"
      aria-label="胜任力雷达图"
      width={size}
      height={size}
      className="mx-auto"
    >
      {/* 同心网格 */}
      {[1, 2, 3, 4, 5].map((level) => {
        const r = (level / LEVEL_MAX) * radius
        const gridPoints = points
          .map((p) => {
            const x = center + Math.cos(p.angle) * r
            const y = center + Math.sin(p.angle) * r
            return `${x},${y}`
          })
          .join(' ')
        return (
          <polygon
            key={level}
            points={gridPoints}
            fill="none"
            stroke="currentColor"
            strokeWidth={0.5}
            className="text-border"
          />
        )
      })}

      {/* 放射线 */}
      {points.map((p, i) => (
        <line
          key={i}
          x1={center}
          y1={center}
          x2={center + Math.cos(p.angle) * radius}
          y2={center + Math.sin(p.angle) * radius}
          stroke="currentColor"
          strokeWidth={0.5}
          className="text-border"
        />
      ))}

      {/* 要求等级多边形 */}
      <path d={requiredPath} fill="rgba(59, 130, 246, 0.1)" stroke="rgb(59, 130, 246)" strokeWidth={1.5} strokeDasharray="4 2" />

      {/* 当前等级多边形 */}
      <path d={currentPath} fill="rgba(16, 185, 129, 0.2)" stroke="rgb(16, 185, 129)" strokeWidth={2} />

      {/* 顶点圆点 */}
      {points.map((p, i) => (
        <circle key={`c-${i}`} cx={p.currentX} cy={p.currentY} r={3} fill="rgb(16, 185, 129)" />
      ))}

      {/* 维度标签 */}
      {points.map((p, i) => (
        <text
          key={`t-${i}`}
          x={p.labelX}
          y={p.labelY}
          textAnchor="middle"
          dominantBaseline="middle"
          className="text-xs fill-text-secondary"
        >
          {p.name}
        </text>
      ))}
    </svg>
  )
}
