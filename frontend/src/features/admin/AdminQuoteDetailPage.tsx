import { Loader2, ShieldCheck, ShieldX } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { errorMessage } from '@/api/errors'
import { useQuote, useVerifyQuote } from '@/api/hooks'
import { EmptyState, ErrorState, LoadingState } from '@/components/common/PageStates'
import { QuoteAnalysisView } from '@/components/quote/QuoteAnalysisView'
import { QuoteContextCard, QuoteHeader } from '@/components/quote/QuoteSummary'
import { QuoteTimeline } from '@/components/quote/QuoteTimeline'
import { SnapshotViewer } from '@/components/quote/SnapshotViewer'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatDateTime } from '@/lib/format'
import { cn } from '@/lib/utils'

export function AdminQuoteDetailPage() {
  const { quoteId } = useParams()
  const query = useQuote(quoteId)
  const verify = useVerifyQuote()

  if (query.isLoading) return <LoadingState />
  if (query.error || !query.data) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  const quote = query.data

  return (
    <div className="space-y-6">
      <QuoteHeader
        quote={quote}
        backTo="/admin/quotes"
        backLabel="Tra cứu hồ sơ"
        actions={
          quote.snapshot && (
            <Button variant="outline" onClick={() => verify.mutate(quote.quoteId)} disabled={verify.isPending}>
              {verify.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />} Kiểm tra toàn vẹn
            </Button>
          )
        }
      />
      {verify.data && (
        <p
          className={cn(
            'inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium',
            verify.data.valid ? 'bg-success/10 text-success' : 'bg-destructive/10 text-destructive',
          )}
          data-testid="verify-result"
        >
          {verify.data.valid ? <ShieldCheck className="h-4 w-4" /> : <ShieldX className="h-4 w-4" />}
          {verify.data.valid ? 'Bản lưu khớp mã băm đã ký' : 'Bản lưu KHÔNG khớp mã băm đã ký'} · {formatDateTime(verify.data.verifiedAt)}
        </p>
      )}
      {verify.isError && <p className="text-sm text-destructive">{errorMessage(verify.error)}</p>}

      <div className="grid gap-6 xl:grid-cols-[1fr,340px]">
        <Tabs defaultValue="analysis" className="min-w-0">
          <TabsList>
            <TabsTrigger value="analysis">Kết quả phân tích</TabsTrigger>
            <TabsTrigger value="snapshot">Bản lưu đã ký</TabsTrigger>
          </TabsList>
          <TabsContent value="analysis">
            <QuoteAnalysisView quote={quote} />
          </TabsContent>
          <TabsContent value="snapshot">
            {quote.snapshot && quote.snapshotHash ? (
              <SnapshotViewer snapshot={quote.snapshot} hash={quote.snapshotHash} />
            ) : (
              <EmptyState title="Hồ sơ chưa được ký duyệt" description="Bản lưu bất biến chỉ được tạo khi Quản lý phê duyệt." />
            )}
          </TabsContent>
        </Tabs>
        <div className="space-y-4">
          <QuoteContextCard quote={quote} />
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Lịch sử xử lý</CardTitle>
            </CardHeader>
            <CardContent>
              <QuoteTimeline events={quote.history} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
