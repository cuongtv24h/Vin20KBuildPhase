import { Target } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { OBJECTIVE_LABEL } from '@/engine/recommend'
import type { RecommendationRecord } from '@/types/domain'

export function RecommendationPanel({ recommendation }: { recommendation: RecommendationRecord }) {
  return (
    <Card className="border-primary/25 bg-primary/[0.03]">
      <CardContent className="flex gap-3 p-4">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <Target className="h-4 w-4" />
        </span>
        <div className="space-y-1">
          <p className="text-xs font-semibold text-primary">
            Tiêu chí tối ưu hóa đã chọn: {OBJECTIVE_LABEL[recommendation.objective]}
          </p>
          <p className="text-sm leading-relaxed text-foreground">{recommendation.rationale}</p>
        </div>
      </CardContent>
    </Card>
  )
}
