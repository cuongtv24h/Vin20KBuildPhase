import { CheckCircle2, Clock, FileEdit, Loader2, Send, XCircle } from 'lucide-react'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'
import type { Quote } from '@pricepolicy/api-client/contracts'
import { ApiError, errorMessage } from '@pricepolicy/api-client/errors'
import { useQuote, useQuoteAudit, useQuoteEvents, useQuoteEvidence, useSubmitQuote } from '@pricepolicy/api-client/hooks'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { ErrorState, LoadingState, QueryState } from '@pricepolicy/ui/components/common/PageStates'
import { PdfStatusBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { MessageComposer } from '@/components/compliance/MessageComposer'
import { AgentProgress } from '@/components/quote/AgentProgress'
import { EvidenceProvider } from '@pricepolicy/ui/components/quote/Evidence'
import { AuditTimeline, ContextCard, QuoteHeader } from '@/components/quote/QuoteMeta'
import { QuoteResults } from '@/components/quote/QuoteResults'
import { StopStatePanel } from '@/components/quote/StopStatePanel'
import { Alert, AlertDescription, AlertTitle } from '@pricepolicy/ui/components/ui/alert'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { formatDateTime, truncateHash } from '@pricepolicy/ui/lib/format'
import { saleActions, stopKindOf } from '@pricepolicy/ui/lib/quoteRules'
import { toast } from '@pricepolicy/ui/state/toastStore'

export function SaleQuoteDetailPage() {
  const { quoteId } = useParams()
  const [params, setParams] = useSearchParams()
  const version = params.get('v') ? Number(params.get('v')) : undefined
  const query = useQuote(quoteId, version)

  if (query.isLoading) return <LoadingState />
  if (!query.data) return <ErrorState error={query.error ?? new Error('Không tìm thấy hồ sơ.')} onRetry={() => query.refetch()} />
  return <QuoteDetail quote={query.data} onRecheck={() => query.refetch()} onVersionChange={(v) => setParams(v ? { v: String(v) } : {})} />
}

function QuoteDetail({ quote, onRecheck, onVersionChange }: { quote: Quote; onRecheck: () => void; onVersionChange: (v: number | undefined) => void }) {
  const user = useCurrentUser()
  const location = useLocation()
  const streamUrl = (location.state as { streamUrl?: string } | null)?.streamUrl
  const progress = useQuoteEvents(quote, streamUrl)
  const analyzing = quote.status === 'ANALYZING'
  const evidence = useQuoteEvidence(quote, !analyzing)
  const audit = useQuoteAudit(quote.quote_id, `${quote.quote_version}:${quote.status}:${quote.pdf_status}`)
  const submit = useSubmitQuote()
  const can = saleActions(quote, user.role)
  const stop = stopKindOf(quote)

  async function handleSubmit() {
    try {
      await submit.mutateAsync({ quote, extra: undefined })
      toast.success('Đã gửi Quản lý duyệt', quote.quote_id)
    } catch (e) {
      toast.error('Không thể gửi duyệt', errorMessage(e))
    }
  }

  const actions = (
    <>
      {can.revise && (
        <Button variant={quote.status === 'DRAFT' ? 'outline' : 'default'} asChild>
          <Link to={`/sale/quotes/${quote.quote_id}/revise`}>
            <FileEdit className="h-4 w-4" /> {quote.status === 'DRAFT' ? 'Điều chỉnh' : 'Chỉnh sửa và phân tích lại'}
          </Link>
        </Button>
      )}
      {can.submit && (
        <Button onClick={handleSubmit} disabled={submit.isPending} data-testid="submit-quote">
          {submit.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Gửi Quản lý duyệt
        </Button>
      )}
    </>
  )

  return (
    <EvidenceProvider claims={evidence.data?.claims}>
      <div className="space-y-6">
        <QuoteHeader quote={quote} backTo="/sale/quotes" backLabel="Báo giá" actions={actions} onVersionChange={onVersionChange} />
        <StatusNotice quote={quote} />

        <div className="grid gap-6 xl:grid-cols-[1fr,340px]">
          <div className="min-w-0 space-y-6">
            {analyzing && <AgentProgress progress={progress} onRecheck={onRecheck} />}
            {stop && <StopStatePanel quote={quote} />}
            {!analyzing && !stop && quote.scenarios.length > 0 && (
              <QueryState query={evidence} loadingLabel="Đang tải chứng cứ…">
                {(ev) => <QuoteResults quote={quote} claims={ev.claims} />}
              </QueryState>
            )}
            {can.compose && <MessageComposer quote={quote} />}
          </div>
          <div className="space-y-4">
            <ContextCard quote={quote} />
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Nhật ký hồ sơ</CardTitle>
              </CardHeader>
              <CardContent>
                {audit.error && audit.data === undefined && audit.error instanceof ApiError && audit.error.status === 404 ? (
                  <p className="text-sm text-muted-foreground">Chưa có hoạt động nào cho hồ sơ này</p>
                ) : audit.error && audit.data === undefined ? (
                  <div className="flex flex-col items-start gap-2">
                    <p className="text-sm text-muted-foreground">Không tải được nhật ký</p>
                    <Button variant="outline" size="sm" onClick={() => audit.refetch()}>
                      Thử lại
                    </Button>
                  </div>
                ) : (
                  <QueryState query={audit}>{(a) => <AuditTimeline audit={a} />}</QueryState>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </EvidenceProvider>
  )
}

function StatusNotice({ quote }: { quote: Quote }) {
  const a = quote.approval
  switch (quote.status) {
    case 'READY_FOR_REVIEW':
      return (
        <Alert variant="info">
          <Clock />
          <AlertTitle>Đang chờ Quản lý duyệt</AlertTitle>
          <AlertDescription>Gửi lúc {quote.submitted_at ? formatDateTime(quote.submitted_at) : '—'}</AlertDescription>
        </Alert>
      )
    case 'NEEDS_REVISION':
      return (
        <Alert variant="warning">
          <FileEdit />
          <AlertTitle>{a?.decided_by.full_name} yêu cầu chỉnh sửa</AlertTitle>
          <AlertDescription className="text-foreground">{a?.reason}</AlertDescription>
        </Alert>
      )
    case 'REJECTED':
      return (
        <Alert variant="destructive" data-testid="rejected-notice">
          <XCircle />
          <AlertTitle>{a?.decided_by.full_name} đã từ chối</AlertTitle>
          <AlertDescription className="text-foreground">{a?.reason}</AlertDescription>
        </Alert>
      )
    case 'APPROVED':
      return (
        <Alert variant="success">
          <CheckCircle2 />
          <AlertTitle>
            {a?.decided_by.full_name} đã phê duyệt lúc {a ? formatDateTime(a.decided_at) : ''}
          </AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2 text-foreground/80">
            {quote.pdf_status && <PdfStatusBadge status={quote.pdf_status} />}
            {quote.artifact_hash && <span className="font-mono text-xs">SHA-256 {truncateHash(quote.artifact_hash, 10)}</span>}
            {a?.reason && <span>· {a.reason}</span>}
          </AlertDescription>
        </Alert>
      )
    default:
      return null
  }
}
