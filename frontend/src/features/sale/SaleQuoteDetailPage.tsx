import {
  CalendarCheck,
  CheckCircle2,
  Clock,
  Copy,
  ExternalLink,
  Eye,
  FileEdit,
  FilePlus2,
  Loader2,
  MessageSquare,
  Send,
  Share2,
  ShieldAlert,
  XCircle,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { errorMessage } from '@/api/errors'
import { useQuote, useShareQuote, useSubmitQuote } from '@/api/hooks'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { ErrorState, LoadingState } from '@/components/common/PageStates'
import { QuoteAnalysisView } from '@/components/quote/QuoteAnalysisView'
import { QuoteContextCard, QuoteHeader } from '@/components/quote/QuoteSummary'
import { QuoteTimeline } from '@/components/quote/QuoteTimeline'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { canPerform } from '@/engine/workflow'
import { formatDate, formatDateTime, truncateHash } from '@/lib/format'
import { CHANNEL_LABEL } from '@/lib/labels'
import { shareUrlFor } from '@/lib/links'
import { toast } from '@/state/toastStore'
import type { Quote, ShareChannel } from '@/types/domain'

export function SaleQuoteDetailPage() {
  const { quoteId } = useParams()
  const user = useCurrentUser()
  const query = useQuote(quoteId)
  const submit = useSubmitQuote()
  const [shareOpen, setShareOpen] = useState(false)

  if (query.isLoading) return <LoadingState />
  if (query.error || !query.data) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  const quote = query.data
  const can = (a: Parameters<typeof canPerform>[0]) => canPerform(a, quote.status, user.role)

  async function handleSubmit() {
    try {
      await submit.mutateAsync(quote.quoteId)
      toast.success('Đã gửi Quản lý duyệt', quote.quoteId)
    } catch (e) {
      toast.error('Không thể gửi duyệt', errorMessage(e))
    }
  }

  const actions = (
    <>
      {can('REVISE') && (
        <Button variant={quote.status === 'NEEDS_REVISION' ? 'default' : 'outline'} asChild>
          <Link to={`/sale/quotes/${quote.quoteId}/revise`}>
            <FileEdit className="h-4 w-4" /> {quote.status === 'NEEDS_REVISION' ? 'Chỉnh sửa & trình lại' : 'Chỉnh sửa'}
          </Link>
        </Button>
      )}
      {can('SUBMIT') && (
        <Button onClick={handleSubmit} disabled={submit.isPending}>
          {submit.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Gửi Quản lý duyệt
        </Button>
      )}
      {can('SHARE') && (
        <Button onClick={() => setShareOpen(true)} variant={quote.distribution ? 'outline' : 'default'}>
          <Share2 className="h-4 w-4" /> {quote.distribution ? 'Gửi lại cho khách' : 'Gửi báo giá cho khách'}
        </Button>
      )}
      {quote.status === 'REJECTED' && (
        <Button asChild>
          <Link to={`/sale/quotes/new?fromQuote=${quote.quoteId}`}>
            <FilePlus2 className="h-4 w-4" /> Lập hồ sơ mới
          </Link>
        </Button>
      )}
    </>
  )

  return (
    <div className="space-y-6">
      <QuoteHeader quote={quote} backTo="/sale/quotes" backLabel="Hồ sơ báo giá" actions={actions} />
      <StatusNotice quote={quote} />

      <div className="grid gap-6 xl:grid-cols-[1fr,340px]">
        <div className="min-w-0 space-y-6">
          <QuoteAnalysisView quote={quote} />
        </div>
        <div className="space-y-4">
          {quote.distribution && <DistributionCard quote={quote} />}
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

      {shareOpen && <ShareDialog quote={quote} onClose={() => setShareOpen(false)} />}
    </div>
  )
}

function StatusNotice({ quote }: { quote: Quote }) {
  switch (quote.status) {
    case 'READY_FOR_REVIEW':
      return (
        <Alert variant="info">
          <Clock />
          <AlertTitle>Đang chờ Quản lý duyệt</AlertTitle>
          <AlertDescription>Bạn sẽ nhận kết quả ngay khi Quản lý ra quyết định.</AlertDescription>
        </Alert>
      )
    case 'ABSTAINED':
      return (
        <Alert variant="destructive">
          <ShieldAlert />
          <AlertTitle>Đang chờ Quản lý thẩm định ngoại lệ</AlertTitle>
          <AlertDescription className="text-foreground/80">
            Hệ thống không tự tính giá cho tập ưu đãi này. Bạn có thể chỉnh sửa để phân tích lại trong khi chờ.
          </AlertDescription>
        </Alert>
      )
    case 'NEEDS_REVISION':
      return (
        <Alert variant="warning">
          <FileEdit />
          <AlertTitle>{quote.approval?.approverName} yêu cầu chỉnh sửa</AlertTitle>
          <AlertDescription className="text-foreground">{quote.approval?.notes}</AlertDescription>
        </Alert>
      )
    case 'REJECTED':
      return (
        <Alert variant="destructive">
          <XCircle />
          <AlertTitle>{quote.approval?.approverName} đã từ chối hồ sơ</AlertTitle>
          <AlertDescription className="text-foreground/80">{quote.approval?.notes}</AlertDescription>
        </Alert>
      )
    case 'APPROVED':
      return (
        <Alert variant="success">
          <CheckCircle2 />
          <AlertTitle>
            Đã được {quote.approval?.approverName} phê duyệt lúc {quote.approval ? formatDateTime(quote.approval.timestamp) : ''}
          </AlertTitle>
          <AlertDescription className="font-mono text-xs text-foreground/70">
            Mã xác thực {quote.snapshotHash ? truncateHash(quote.snapshotHash, 12) : ''}
          </AlertDescription>
        </Alert>
      )
    default:
      return null
  }
}

function DistributionCard({ quote }: { quote: Quote }) {
  const d = quote.distribution
  if (!d) return null
  const url = shareUrlFor(d.shareToken)
  const response = d.customerResponse
  return (
    <Card className="border-gold/40" data-testid="distribution-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Đã gửi khách</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <p className="text-muted-foreground">
          Qua {CHANNEL_LABEL[d.channel]} · {formatDateTime(d.sharedAt)} · hiệu lực đến {formatDate(d.expiresAt)}
        </p>
        <p className="inline-flex items-center gap-1.5">
          <Eye className="h-3.5 w-3.5 text-muted-foreground" />
          {d.viewedAt ? `Khách đã xem lúc ${formatDateTime(d.viewedAt)}` : 'Khách chưa mở báo giá'}
        </p>
        {response && (
          <div className="rounded-md bg-success/10 p-2.5">
            <p className="inline-flex items-center gap-1.5 font-medium text-success">
              {response.decision === 'ACCEPTED' ? <CalendarCheck className="h-4 w-4" /> : <MessageSquare className="h-4 w-4" />}
              {response.decision === 'ACCEPTED' ? 'Khách đồng ý & muốn đặt lịch ký cọc' : 'Khách cần tư vấn thêm'}
            </p>
            {response.preferredAppointment && <p className="mt-1">Lịch hẹn: {formatDateTime(response.preferredAppointment)}</p>}
            {response.note && <p className="mt-1">{response.note}</p>}
          </div>
        )}
        <div className="flex gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigator.clipboard?.writeText(url).then(() => toast.success('Đã sao chép đường dẫn'))}
          >
            <Copy className="h-3.5 w-3.5" /> Sao chép link
          </Button>
          <Button variant="outline" size="sm" asChild>
            <a href={url} target="_blank" rel="noreferrer">
              <ExternalLink className="h-3.5 w-3.5" /> Mở trang khách
            </a>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function ShareDialog({ quote, onClose }: { quote: Quote; onClose: () => void }) {
  const share = useShareQuote()
  const [channel, setChannel] = useState<ShareChannel>(quote.distribution?.channel ?? 'ZALO')
  const sharedUrl = share.data?.distribution ? shareUrlFor(share.data.distribution.shareToken) : null
  const message = `VLandFuture kính gửi anh/chị ${quote.context.customerName} báo giá chính thức căn hộ ${quote.unit.unitCode} (${quote.unit.projectName}).`

  async function handleShare() {
    try {
      await share.mutateAsync({ quoteId: quote.quoteId, channel })
      toast.success('Đã gửi báo giá cho khách', `${CHANNEL_LABEL[channel]} · ${quote.context.customerPhone}`)
    } catch (e) {
      toast.error('Không thể gửi báo giá', errorMessage(e))
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Gửi báo giá cho khách</DialogTitle>
          <DialogDescription>
            {quote.context.customerName} · {quote.context.customerPhone}
          </DialogDescription>
        </DialogHeader>

        {!sharedUrl ? (
          <>
            <RadioGroup value={channel} onValueChange={(v) => setChannel(v as ShareChannel)} className="grid grid-cols-3 gap-2">
              {(Object.keys(CHANNEL_LABEL) as ShareChannel[]).map((c) => (
                <label key={c} className="flex cursor-pointer items-center gap-2 rounded-md border border-border p-2.5 text-sm">
                  <RadioGroupItem value={c} /> {CHANNEL_LABEL[c]}
                </label>
              ))}
            </RadioGroup>
            <p className="rounded-md bg-muted/60 p-3 text-sm">{message}</p>
            {share.isError && <p className="text-sm text-destructive">{errorMessage(share.error)}</p>}
            <DialogFooter>
              <Button variant="outline" onClick={onClose}>
                Huỷ
              </Button>
              <Button onClick={handleShare} disabled={share.isPending}>
                {share.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />} Gửi
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="flex items-center gap-2 rounded-md bg-success/10 p-3 text-sm text-success">
              <CheckCircle2 className="h-4 w-4" /> Đã gửi qua {CHANNEL_LABEL[channel]}
            </div>
            <div className="flex gap-2">
              <Input readOnly value={sharedUrl} className="font-mono text-xs" data-testid="share-url" />
              <Button variant="outline" size="icon" onClick={() => navigator.clipboard?.writeText(sharedUrl)} aria-label="Sao chép">
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            <DialogFooter>
              <Button variant="outline" asChild>
                <a href={sharedUrl} target="_blank" rel="noreferrer">
                  <ExternalLink className="h-4 w-4" /> Mở trang khách
                </a>
              </Button>
              <Button onClick={onClose}>Xong</Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
