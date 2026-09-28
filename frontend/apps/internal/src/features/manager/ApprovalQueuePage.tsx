import { ClipboardCheck } from 'lucide-react'
import type { Quote, QuoteWorkflowStatus, RiskFlagColor } from '@pricepolicy/api-client/contracts'
import { useQuotes } from '@pricepolicy/api-client/hooks'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { EmptyState, PageHeader, QueryState } from '@pricepolicy/ui/components/common/PageStates'
import { QuoteTable } from '@/components/quote/QuoteTable'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@pricepolicy/ui/components/ui/tabs'

const RISK: Record<RiskFlagColor, number> = { RED: 0, YELLOW: 1, GREEN: 2 }

/** Rủi ro cao trước; cùng mức thì hồ sơ chờ lâu hơn trước. */
const byPriority = (a: Quote, b: Quote) => RISK[a.risk_flag.color] - RISK[b.risk_flag.color] || (a.submitted_at ?? a.updated_at).localeCompare(b.submitted_at ?? b.updated_at)

const TABS: { key: string; label: string; statuses: QuoteWorkflowStatus[] }[] = [
  { key: 'review', label: 'Chờ duyệt', statuses: ['READY_FOR_REVIEW'] },
  { key: 'exception', label: 'Ngoại lệ', statuses: ['ABSTAINED'] },
  { key: 'done', label: 'Đã xử lý', statuses: ['APPROVED', 'REJECTED', 'NEEDS_REVISION'] },
]

export function ApprovalQueuePage() {
  const user = useCurrentUser()
  const quotes = useQuotes({ status: TABS.flatMap((t) => t.statuses) }, { live: true })
  return (
    <div className="space-y-6">
      <PageHeader title="Phê duyệt báo giá" />
      <QueryState query={quotes} isEmpty={(d) => d.length === 0} empty={<EmptyState icon={ClipboardCheck} title="Không có hồ sơ" />}>
        {(data) => (
          <Tabs defaultValue="review">
            <TabsList>
              {TABS.map((t) => (
                <TabsTrigger key={t.key} value={t.key}>
                  {t.label} ({data.filter((q) => t.statuses.includes(q.status)).length})
                </TabsTrigger>
              ))}
            </TabsList>
            {TABS.map((t) => {
              const rows = data.filter((q) => t.statuses.includes(q.status)).sort(t.key === 'done' ? (a, b) => b.updated_at.localeCompare(a.updated_at) : byPriority)
              return (
                <TabsContent key={t.key} value={t.key}>
                  {rows.length === 0 ? (
                    <EmptyState icon={ClipboardCheck} title="Không có hồ sơ" />
                  ) : (
                    <QuoteTable quotes={rows} hrefFor={(q) => `/manager/approvals/${q.quote_id}`} showOwner sodUserId={user.user_id} />
                  )}
                </TabsContent>
              )
            })}
          </Tabs>
        )}
      </QueryState>
    </div>
  )
}
