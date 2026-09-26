import { FilePlus2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuotes } from '@/api/hooks'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '@/components/common/PageStates'
import { QuoteTable } from '@/components/quote/QuoteTable'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { WorkflowStatus } from '@/types/domain'

const GROUPS: { key: string; label: string; statuses: WorkflowStatus[] | null }[] = [
  { key: 'all', label: 'Tất cả', statuses: null },
  { key: 'todo', label: 'Cần xử lý', statuses: ['DRAFT', 'NEEDS_REVISION', 'CALCULATION_FAILED'] },
  { key: 'review', label: 'Chờ Quản lý', statuses: ['READY_FOR_REVIEW', 'ABSTAINED'] },
  { key: 'approved', label: 'Đã duyệt', statuses: ['APPROVED'] },
  { key: 'rejected', label: 'Từ chối', statuses: ['REJECTED'] },
]

export function SaleQuotesPage() {
  const quotes = useQuotes()
  const [group, setGroup] = useState('all')
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    const statuses = GROUPS.find((g) => g.key === group)?.statuses
    const term = search.trim().toLowerCase()
    return (quotes.data ?? []).filter(
      (q) =>
        (!statuses || statuses.includes(q.status)) &&
        (!term || [q.quoteId, q.context.customerName, q.unit.unitCode, q.context.customerPhone].some((v) => v.toLowerCase().includes(term))),
    )
  }, [quotes.data, group, search])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hồ sơ báo giá"
        actions={
          <Button asChild>
            <Link to="/sale/quotes/new">
              <FilePlus2 className="h-4 w-4" /> Lập báo giá
            </Link>
          </Button>
        }
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs value={group} onValueChange={setGroup}>
          <TabsList>
            {GROUPS.map((g) => (
              <TabsTrigger key={g.key} value={g.key}>
                {g.label} ({(quotes.data ?? []).filter((q) => !g.statuses || g.statuses.includes(q.status)).length})
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <Input className="max-w-xs" placeholder="Tìm mã hồ sơ, khách hàng, căn hộ…" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>
      {quotes.isLoading && <LoadingState />}
      {quotes.error && <ErrorState error={quotes.error} onRetry={() => quotes.refetch()} />}
      {quotes.data && (filtered.length === 0 ? <EmptyState title="Không có hồ sơ phù hợp" /> : <QuoteTable quotes={filtered} hrefFor={(id) => `/sale/quotes/${id}`} />)}
    </div>
  )
}
