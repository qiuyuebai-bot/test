import type { PositionDetail } from '@/types/training'
interface Props { position: PositionDetail | null; learnerId: number | null }
export default function EmbeddedResourceGeneration({ position, learnerId }: Props) {
  return <div data-testid="embedded-resource-placeholder" />
}
