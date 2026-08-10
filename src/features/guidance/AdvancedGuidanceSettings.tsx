import type { FormEvent } from 'react'
import Input from '@/components/Input'
import Button from '@/components/Button'

interface AdvancedGuidanceSettingsProps {
  topic: string
  difficulty: string
  questionCount: string
  loading: boolean
  onTopicChange: (value: string) => void
  onDifficultyChange: (value: string) => void
  onQuestionCountChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

export default function AdvancedGuidanceSettings({
  topic,
  difficulty,
  questionCount,
  loading,
  onTopicChange,
  onDifficultyChange,
  onQuestionCountChange,
  onSubmit,
}: AdvancedGuidanceSettingsProps) {
  return (
    <details className="rounded-lg border border-border/70 bg-bg-secondary/30 px-4 py-3">
      <summary className="cursor-pointer text-sm font-medium text-text-primary">高级设置</summary>
      <form onSubmit={onSubmit} noValidate className="mt-4 space-y-4">
        <Input
          label="主题关键词"
          value={topic}
          onChange={(event) => onTopicChange(event.target.value)}
          placeholder="留空时使用系统推荐主题"
          maxLength={200}
          disabled={loading}
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label="目标难度（1–5，可留空）"
            type="number"
            min={1}
            max={5}
            step={1}
            value={difficulty}
            onChange={(event) => onDifficultyChange(event.target.value)}
            placeholder="按学习者画像自动匹配"
            disabled={loading}
          />
          <Input
            label="题量（1–10）"
            type="number"
            min={1}
            max={10}
            step={1}
            value={questionCount}
            onChange={(event) => onQuestionCountChange(event.target.value)}
            disabled={loading}
          />
        </div>
        <Button type="submit" variant="outline" loading={loading} disabled={loading}>
          生成导学题目
        </Button>
      </form>
    </details>
  )
}
