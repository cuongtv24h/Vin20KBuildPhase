import { AlertOctagon, Building2, CalendarDays, User } from 'lucide-react'
import { ActivePolicyBanner, ConflictBanner } from '@/components/ConflictBanner'
import { RecommendationPanel } from '@/components/RecommendationPanel'
import { RiskFlagBadge } from '@/components/RiskFlagBadge'
import { ScenarioCard } from '@/components/ScenarioCard'
import { WorkflowStatusBadge } from '@/components/StatusBadge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import { formatDate, formatDateTime, truncateHash } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { Quote } from '@/types/domain'

const SEGMENT_LABEL: Record<Quote['context']['customerSegment'], string> = {
  EXISTING_RESIDENT: 'Cư dân hiện hữu',
  NEW_CUSTOMER: 'Khách hàng mới',
}

export function QuoteDetail({ quote, className }: { quote: Quote; className?: string }) {
  return (
    <div className={cn('space-y-5', className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-display text-xl font-semibold tracking-tight">{quote.quoteId}</p>
            <WorkflowStatusBadge status={quote.status} />
          </div>
          <RiskFlagBadge flag={quote.riskFlag} />
        </div>
        <div className="grid grid-cols-1 gap-1 text-sm text-muted-foreground sm:grid-cols-3 sm:gap-4">
          <span className="inline-flex items-center gap-1.5">
            <Building2 className="h-3.5 w-3.5" /> {quote.unit.unitCode} · {quote.unit.projectName}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <User className="h-3.5 w-3.5" /> {quote.context.customerName} ({SEGMENT_LABEL[quote.context.customerSegment]})
          </span>
          <span className="inline-flex items-center gap-1.5">
            <CalendarDays className="h-3.5 w-3.5" /> Giao dịch {formatDate(quote.context.transactionDate)}
          </span>
        </div>
      </div>

      {quote.preflight?.activePolicy && !quote.preflight.hasBlockingIssue && (
        <ActivePolicyBanner
          policy={{
            title: quote.preflight.activePolicy.title,
            version: quote.preflight.activePolicy.version,
            effectiveFrom: quote.preflight.activePolicy.effectiveFrom,
            effectiveTo: quote.preflight.activePolicy.effectiveTo,
          }}
        />
      )}

      {quote.status === 'ABSTAINED' && quote.preflight && <ConflictBanner preflight={quote.preflight} />}

      {quote.status === 'CALCULATION_FAILED' && (
        <Alert variant="destructive">
          <AlertOctagon />
          <AlertTitle>Kết quả tính toán không đạt chuẩn đối soát</AlertTitle>
          <AlertDescription>
            <p className="mb-2">
              Deterministic Financial Validation Gate đã chặn đứng kết quả trước khi hiển thị cho khách hàng. Báo giá
              không được phép phát hành.
            </p>
            <ul className="list-inside list-disc space-y-0.5">
              {quote.scenarios[0]?.validation.reasons.map((reason) => <li key={reason}>{reason}</li>)}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {quote.scenarios.length > 0 && quote.status !== 'CALCULATION_FAILED' && (
        <>
          {quote.recommendation && <RecommendationPanel recommendation={quote.recommendation} />}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
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

      {quote.approval && (
        <>
          <Separator />
          <div className="rounded-lg border border-border p-4">
            <p className="text-sm font-semibold">
              Bản ghi phê duyệt —{' '}
              {quote.approval.decision === 'APPROVED'
                ? 'Đã phê duyệt'
                : quote.approval.decision === 'REJECTED'
                  ? 'Đã từ chối'
                  : 'Yêu cầu chỉnh sửa'}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {quote.approval.approverName} · {formatDateTime(quote.approval.timestamp)}
            </p>
            {quote.approval.notes && <p className="mt-2 text-sm leading-relaxed">{quote.approval.notes}</p>}
            {quote.snapshotHash && (
              <p className="mt-2 font-mono text-xs text-muted-foreground">
                SHA-256 Snapshot: {truncateHash(quote.snapshotHash, 12)}
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
