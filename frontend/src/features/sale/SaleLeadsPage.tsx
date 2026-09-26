import { FilePlus2, Hand, Loader2, Mail, Phone } from 'lucide-react'
import { useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { errorMessage } from '@/api/errors'
import { useClaimLead, useLeads, useQuotes } from '@/api/hooks'
import { EmptyState, ErrorState, LoadingState, PageHeader } from '@/components/common/PageStates'
import { LeadStatusBadge, WorkflowStatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatRelative } from '@/lib/format'
import { OBJECTIVE_SHORT_LABEL, SEGMENT_LABEL } from '@/lib/labels'
import { toast } from '@/state/toastStore'
import type { Lead, Quote } from '@/types/domain'

export function SaleLeadsPage() {
  const unassigned = useLeads({ scope: 'UNASSIGNED' })
  const mine = useLeads({ scope: 'MINE' })
  const quotes = useQuotes()

  const quotesByLead = useMemo(() => {
    const map = new Map<string, Quote>()
    for (const q of quotes.data ?? []) if (q.leadId && !map.has(q.leadId)) map.set(q.leadId, q)
    return map
  }, [quotes.data])

  return (
    <div className="space-y-6">
      <PageHeader title="Yêu cầu khách hàng" description="Yêu cầu báo giá gửi từ website và hotline." />
      <Tabs defaultValue="unassigned">
        <TabsList>
          <TabsTrigger value="unassigned">Chờ tiếp nhận ({unassigned.data?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="mine">Tôi phụ trách ({mine.data?.length ?? 0})</TabsTrigger>
        </TabsList>
        <TabsContent value="unassigned">
          <LeadList query={unassigned} quotesByLead={quotesByLead} emptyTitle="Không có yêu cầu mới" />
        </TabsContent>
        <TabsContent value="mine">
          <LeadList query={mine} quotesByLead={quotesByLead} emptyTitle="Bạn chưa phụ trách yêu cầu nào" />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function LeadList({
  query,
  quotesByLead,
  emptyTitle,
}: {
  query: ReturnType<typeof useLeads>
  quotesByLead: Map<string, Quote>
  emptyTitle: string
}) {
  if (query.isLoading) return <LoadingState />
  if (query.error) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  if (!query.data?.length) return <EmptyState title={emptyTitle} />
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {query.data.map((lead) => (
        <LeadCard key={lead.leadId} lead={lead} quote={quotesByLead.get(lead.leadId)} />
      ))}
    </div>
  )
}

function LeadCard({ lead, quote }: { lead: Lead; quote?: Quote }) {
  const claim = useClaimLead()
  const navigate = useNavigate()

  async function handleClaim(thenQuote: boolean) {
    try {
      await claim.mutateAsync(lead.leadId)
      toast.success('Đã tiếp nhận yêu cầu', `${lead.fullName} · ${lead.phone}`)
      if (thenQuote) navigate(`/sale/quotes/new?leadId=${lead.leadId}`)
    } catch (e) {
      toast.error('Không thể tiếp nhận', errorMessage(e))
    }
  }

  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm" data-lead-id={lead.leadId}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold">{lead.fullName}</p>
          <p className="text-xs text-muted-foreground">
            {lead.leadId} · {formatRelative(lead.createdAt)}
          </p>
        </div>
        <LeadStatusBadge status={lead.status} />
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <p className="inline-flex items-center gap-1.5">
          <Phone className="h-3.5 w-3.5 text-muted-foreground" /> {lead.phone}
        </p>
        {lead.email && (
          <p className="inline-flex min-w-0 items-center gap-1.5">
            <Mail className="h-3.5 w-3.5 shrink-0 text-muted-foreground" /> <span className="truncate">{lead.email}</span>
          </p>
        )}
        <p>
          <span className="text-muted-foreground">Căn quan tâm:</span> <span className="font-medium">{lead.unitCode}</span>
        </p>
        <p>
          <span className="text-muted-foreground">Ưu tiên:</span> {OBJECTIVE_SHORT_LABEL[lead.objective]}
        </p>
        <p className="col-span-2 text-muted-foreground">{SEGMENT_LABEL[lead.customerSegment]}</p>
      </div>
      {lead.note && <p className="rounded-md bg-muted/60 px-3 py-2 text-sm">{lead.note}</p>}
      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border pt-3">
        {!lead.assignedSaleId && (
          <>
            <Button variant="outline" size="sm" onClick={() => handleClaim(false)} disabled={claim.isPending}>
              {claim.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Hand className="h-4 w-4" />} Tiếp nhận
            </Button>
            <Button size="sm" onClick={() => handleClaim(true)} disabled={claim.isPending}>
              <FilePlus2 className="h-4 w-4" /> Tiếp nhận & lập báo giá
            </Button>
          </>
        )}
        {lead.assignedSaleId && quote && (
          <Link to={`/sale/quotes/${quote.quoteId}`} className="inline-flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">{quote.quoteId}</span>
            <WorkflowStatusBadge status={quote.status} />
          </Link>
        )}
        {lead.assignedSaleId && !quote && (
          <Button asChild size="sm">
            <Link to={`/sale/quotes/new?leadId=${lead.leadId}`}>
              <FilePlus2 className="h-4 w-4" /> Lập báo giá
            </Link>
          </Button>
        )}
      </div>
    </div>
  )
}
