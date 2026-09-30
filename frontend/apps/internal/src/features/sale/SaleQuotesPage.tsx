import { FilePlus2, FileStack } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Quote, QuoteWorkflowStatus } from '@pricepolicy/api-client/contracts'
import { useQuotes } from '@pricepolicy/api-client/hooks'
import { EmptyState, PageHeader, QueryState } from '@pricepolicy/ui/components/common/PageStates'
import { QuoteTable } from '@/components/quote/QuoteTable'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@pricepolicy/ui/components/ui/tabs'

const GROUPS: { key: string; label: string; statuses: QuoteWorkflowStatus[] | null }[] = [
  { key: 'action', label: 'Cần xử lý', statuses: ['DRAFT', 'NEEDS_INPUT', 'NEEDS_REVISION', 'ABSTAINED', 'CALCULATION_FAILED', 'ANALYZING'] },
  { key: 'review', label: 'Chờ duyệt', statuses: ['READY_FOR_REVIEW'] },
  { key: 'approved', label: 'Đã duyệt', statuses: ['APPROVED'] },
  { key: 'rejected', label: 'Từ chối', statuses: ['REJECTED'] },
  { key: 'all', label: 'Tất cả', statuses: null },
]

export function SaleQuotesPage() {
  const quotes = useQuotes({}, { live: true })
  return (
    <div className="space-y-6">
      <PageHeader
        title="Báo giá"
        actions={
          <Button asChild>
            <Link to="/sale/quotes/new">
              <FilePlus2 className="h-4 w-4" /> Báo giá khách tại sàn
            </Link>
          </Button>
        }
      />
      <QueryState query={quotes} isEmpty={(d) => d.length === 0} empty={<EmptyState icon={FileStack} title="Chưa có báo giá" />}>
        {(data) => (
          <Tabs defaultValue="action">
            <TabsList className="flex-wrap">
              {GROUPS.map((g) => (
                <TabsTrigger key={g.key} value={g.key}>
                  {g.label} ({filter(data, g.statuses).length})
                </TabsTrigger>
              ))}
            </TabsList>
            {GROUPS.map((g) => (
              <TabsContent key={g.key} value={g.key}>
                {filter(data, g.statuses).length === 0 ? (
                  <EmptyState title="Không có hồ sơ" />
                ) : (
                  <QuoteTable quotes={filter(data, g.statuses)} hrefFor={(q) => `/sale/quotes/${q.quote_id}`} />
                )}
              </TabsContent>
            ))}
          </Tabs>
        )}
      </QueryState>
    </div>
  )
}

const filter = (quotes: Quote[], statuses: QuoteWorkflowStatus[] | null) => (statuses ? quotes.filter((q) => statuses.includes(q.status)) : quotes)
