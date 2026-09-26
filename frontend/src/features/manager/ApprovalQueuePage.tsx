import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuotes } from '@/api/hooks'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '@/components/common/PageStates'
import { QuoteTable } from '@/components/quote/QuoteTable'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { sortQueue } from '@/features/manager/queue'
import type { Quote } from '@/types/domain'

const TABS: { key: string; label: string; filter: (q: Quote) => boolean; empty: string }[] = [
  { key: 'review', label: 'Chờ duyệt', filter: (q) => q.status === 'READY_FOR_REVIEW', empty: 'Không có hồ sơ chờ duyệt' },
  { key: 'exception', label: 'Thẩm định ngoại lệ', filter: (q) => q.status === 'ABSTAINED', empty: 'Không có hồ sơ ngoại lệ' },
  {
    key: 'done',
    label: 'Đã xử lý',
    filter: (q) => ['APPROVED', 'REJECTED', 'NEEDS_REVISION'].includes(q.status),
    empty: 'Chưa có quyết định nào',
  },
]

export function ApprovalQueuePage() {
  const quotes = useQuotes()
  const [params, setParams] = useSearchParams()
  const tab = TABS.find((t) => t.key === params.get('tab')) ?? TABS[0]

  const rows = useMemo(() => {
    const filtered = (quotes.data ?? []).filter(tab.filter)
    return tab.key === 'done' ? filtered : sortQueue(filtered)
  }, [quotes.data, tab])

  return (
    <div className="space-y-6">
      <PageHeader title="Phê duyệt báo giá" description="Sắp xếp theo mức rủi ro, sau đó theo thời gian chờ." />
      <Tabs value={tab.key} onValueChange={(v) => setParams({ tab: v }, { replace: true })}>
        <TabsList>
          {TABS.map((t) => (
            <TabsTrigger key={t.key} value={t.key}>
              {t.label} ({(quotes.data ?? []).filter(t.filter).length})
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {quotes.isLoading && <LoadingState />}
      {quotes.error && <ErrorState error={quotes.error} onRetry={() => quotes.refetch()} />}
      {quotes.data &&
        (rows.length === 0 ? (
          <EmptyState title={tab.empty} />
        ) : (
          <QuoteTable quotes={rows} hrefFor={(id) => `/manager/approvals/${id}`} showOwner showRisk />
        ))}
    </div>
  )
}
