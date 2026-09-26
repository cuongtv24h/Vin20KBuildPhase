import { useMemo, useState } from 'react'
import { useQuotes } from '@/api/hooks'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '@/components/common/PageStates'
import { QuoteTable } from '@/components/quote/QuoteTable'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { WORKFLOW_STATUS_LABEL } from '@/lib/labels'
import type { WorkflowStatus } from '@/types/domain'

export function AdminQuotesPage() {
  const quotes = useQuotes()
  const [status, setStatus] = useState<'ALL' | WorkflowStatus>('ALL')
  const [search, setSearch] = useState('')

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase()
    return (quotes.data ?? []).filter(
      (q) =>
        (status === 'ALL' || q.status === status) &&
        (!term ||
          [q.quoteId, q.context.customerName, q.unit.unitCode, q.ownerName, q.snapshotHash ?? ''].some((v) => v.toLowerCase().includes(term))),
    )
  }, [quotes.data, status, search])

  return (
    <div className="space-y-6">
      <PageHeader title="Tra cứu hồ sơ" description="Toàn bộ hồ sơ báo giá, kể cả bị từ chối hoặc dừng an toàn, kèm bản lưu đã ký." />
      <div className="flex flex-wrap gap-2">
        <Input className="max-w-sm" placeholder="Mã hồ sơ, khách hàng, căn hộ, chuyên viên, mã SHA-256…" value={search} onChange={(e) => setSearch(e.target.value)} />
        <Select value={status} onValueChange={(v) => setStatus(v as typeof status)}>
          <SelectTrigger className="w-52">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ALL">Mọi trạng thái</SelectItem>
            {(Object.keys(WORKFLOW_STATUS_LABEL) as WorkflowStatus[]).map((s) => (
              <SelectItem key={s} value={s}>
                {WORKFLOW_STATUS_LABEL[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {quotes.isLoading && <LoadingState />}
      {quotes.error && <ErrorState error={quotes.error} onRetry={() => quotes.refetch()} />}
      {quotes.data && (rows.length === 0 ? <EmptyState title="Không tìm thấy hồ sơ" /> : <QuoteTable quotes={rows} hrefFor={(id) => `/admin/quotes/${id}`} showOwner showRisk />)}
    </div>
  )
}
