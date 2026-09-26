import { AlertOctagon } from 'lucide-react'
import { ActivePolicyBanner, PreflightFindings } from '@/components/quote/PreflightFindings'
import { RecommendationPanel } from '@/components/quote/RecommendationPanel'
import { ScenarioCard } from '@/components/quote/ScenarioCard'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import type { Quote } from '@/types/domain'

type AnalysisFields = Pick<Quote, 'status' | 'preflight' | 'scenarios' | 'recommendation'>

/** Kết quả phân tích của một phiên bản hồ sơ: chính sách, xung đột, 3 phương án, đề xuất. */
export function QuoteAnalysisView({ quote }: { quote: AnalysisFields }) {
  const failedReasons = Array.from(new Set(quote.scenarios.flatMap((s) => s.validation.reasons)))

  return (
    <div className="space-y-4">
      {quote.preflight?.activePolicy && <ActivePolicyBanner policy={quote.preflight.activePolicy} />}

      {quote.status === 'ABSTAINED' && quote.preflight && <PreflightFindings preflight={quote.preflight} />}

      {quote.status === 'CALCULATION_FAILED' && (
        <Alert variant="destructive">
          <AlertOctagon />
          <AlertTitle>Kết quả tính toán không hợp lệ</AlertTitle>
          <AlertDescription>
            <p className="mb-2 text-foreground/80">Báo giá bị chặn phát hành. Kiểm tra lại dữ liệu đầu vào và phân tích lại.</p>
            <ul className="list-inside list-disc space-y-0.5 text-foreground/80">
              {failedReasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {quote.scenarios.length > 0 && quote.status !== 'CALCULATION_FAILED' && (
        <>
          {quote.recommendation && <RecommendationPanel recommendation={quote.recommendation} />}
          <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-4">
            {quote.scenarios.map((scenario) => (
              <ScenarioCard
                key={scenario.plan}
                scenario={scenario}
                isRecommended={quote.recommendation?.recommendedPlan === scenario.plan}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
