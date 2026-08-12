import type { PositionDetail } from '@/types/training'
interface Props { position: PositionDetail | null; learnerId: number | null }
export default function EmbeddedAdaptivePractice({ position, learnerId }: Props) {
  return <div data-testid="embedded-practice-placeholder" />
}
