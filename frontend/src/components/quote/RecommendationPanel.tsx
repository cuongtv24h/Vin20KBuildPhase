import { Target } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { OBJECTIVE_SHORT_LABEL } from '@/lib/labels'
import type { RecommendationRecord } from '@/types/domain'

export function RecommendationPanel({ recommendation }: { recommendation: RecommendationRecord }) {
  return (
    <Card className="border-gold/40 bg-gold/[0.06]">
      <CardContent className="flex gap-3 p-4">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-gold/15 text-gold">
          <Target className="h-4 w-4" />
        </span>
        <div className="space-y-1">
          <p className="text-xs font-semibold text-gold">Mục tiêu của khách: {OBJECTIVE_SHORT_LABEL[recommendation.objective]}</p>
          <p className="text-sm leading-relaxed text-foreground">{recommendation.rationale}</p>
        </div>
      </CardContent>
    </Card>
  )
}
