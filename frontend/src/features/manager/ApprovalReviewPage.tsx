import { CheckCircle2, FileEdit, Loader2, PenLine, ShieldAlert, XCircle } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { ApprovalDecisionRequest } from '@/api/contracts'
import { errorMessage } from '@/api/errors'
import { useDecideQuote, useQuote, useQuotes } from '@/api/hooks'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { MoneyText } from '@/components/common/MoneyText'
import { ErrorState, LoadingState } from '@/components/common/PageStates'
import { QuoteAnalysisView } from '@/components/quote/QuoteAnalysisView'
import { QuoteContextCard, QuoteHeader } from '@/components/quote/QuoteSummary'
import { QuoteTimeline } from '@/components/quote/QuoteTimeline'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { MANAGER_QUEUE_STATUSES, canPerform } from '@/engine/workflow'
import { sortQueue } from '@/features/manager/queue'
import { formatDateTime, truncateHash } from '@/lib/format'
import { toast } from '@/state/toastStore'
import type { Quote } from '@/types/domain'

const NOTE_TEMPLATES = [
  'Bổ sung chứng từ chứng minh khách hàng hiện hữu.',
  'Chỉ giữ một trong hai ưu đãi loại trừ nhau theo chính sách.',
  'Cập nhật đúng số lượng căn khách đăng ký mua.',
  'Điều khoản chưa đủ căn cứ áp dụng, bỏ khỏi đề nghị.',
]

export function ApprovalReviewPage() {
  const { quoteId } = useParams()
  const query = useQuote(quoteId)

  if (query.isLoading) return <LoadingState />
  if (query.error || !query.data) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  const quote = query.data

  return (
    <div className="space-y-6">
      <QuoteHeader quote={quote} backTo="/manager/approvals" backLabel="Hàng đợi phê duyệt" />
      <div className="grid gap-6 xl:grid-cols-[1fr,360px]">
        <div className="min-w-0">
          <QuoteAnalysisView quote={quote} />
        </div>
        <div className="space-y-4">
          <DecisionPanel key={`${quote.quoteId}-${quote.version}-${quote.status}`} quote={quote} />
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

function DecisionPanel({ quote }: { quote: Quote }) {
  const user = useCurrentUser()
  const navigate = useNavigate()
  const decide = useDecideQuote()
  const queue = useQuotes({ status: MANAGER_QUEUE_STATUSES })
  const [notes, setNotes] = useState('')
  const [confirmApprove, setConfirmApprove] = useState(false)

  const canApprove = canPerform('APPROVE', quote.status, user.role)
  const canReturn = canPerform('REQUEST_REVISION', quote.status, user.role)
  const recommended = quote.scenarios.find((s) => s.plan === quote.recommendation?.recommendedPlan)

  if (!canReturn && !canApprove) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Quyết định</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm">
          {quote.approval ? (
            <>
              <p className="font-medium">
                {quote.approval.decision === 'APPROVED' ? 'Đã phê duyệt' : quote.approval.decision === 'REJECTED' ? 'Đã từ chối' : 'Đã yêu cầu chỉnh sửa'}
              </p>
              <p className="text-muted-foreground">
                {quote.approval.approverName} · {formatDateTime(quote.approval.timestamp)}
              </p>
              {quote.approval.notes && <p className="rounded-md bg-muted/60 p-2">{quote.approval.notes}</p>}
              {quote.snapshotHash && <p className="font-mono text-xs text-muted-foreground">{truncateHash(quote.snapshotHash, 12)}</p>}
            </>
          ) : (
            <p className="text-muted-foreground">Hồ sơ chưa được gửi duyệt.</p>
          )}
        </CardContent>
      </Card>
    )
  }

  async function run(input: ApprovalDecisionRequest) {
    try {
      const result = await decide.mutateAsync({ quoteId: quote.quoteId, ...input })
      const label = input.decision === 'APPROVED' ? 'Đã phê duyệt & ký số' : input.decision === 'REJECTED' ? 'Đã từ chối' : 'Đã trả hồ sơ cho Sale'
      toast.success(label, `${result.quoteId} · ${result.ownerName}`)
      const next = sortQueue((queue.data ?? []).filter((q) => q.quoteId !== quote.quoteId))[0]
      navigate(next ? `/manager/approvals/${next.quoteId}` : '/manager/approvals')
    } catch (e) {
      toast.error('Không thể lưu quyết định', errorMessage(e))
    } finally {
      setConfirmApprove(false)
    }
  }

  const needsNote = notes.trim().length === 0

  return (
    <Card className="border-primary/30 shadow-md" data-testid="decision-panel">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Quyết định của bạn</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {quote.status === 'ABSTAINED' && (
          <p className="flex gap-2 rounded-md bg-destructive/5 p-2.5 text-sm text-destructive">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            Hồ sơ chưa có giá tính tự động. Trả Sale chỉnh sửa theo hướng dẫn hoặc từ chối.
          </p>
        )}
        {recommended && (
          <div className="rounded-md bg-muted/60 p-3">
            <p className="text-xs text-muted-foreground">Phương án đề xuất · {recommended.planLabel}</p>
            <MoneyText amount={recommended.netPrice} size="lg" />
          </div>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="decision-notes">Ghi chú cho Sale</Label>
          <Textarea id="decision-notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
          <div className="flex flex-wrap gap-1.5">
            {NOTE_TEMPLATES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setNotes((n) => (n ? `${n} ${t}` : t))}
                className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                {t}
              </button>
            ))}
          </div>
        </div>
        <div className="grid gap-2">
          {canApprove && (
            <Button variant="success" onClick={() => setConfirmApprove(true)} disabled={decide.isPending}>
              <CheckCircle2 className="h-4 w-4" /> Phê duyệt
            </Button>
          )}
          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="outline"
              onClick={() => run({ decision: 'NEEDS_REVISION', notes })}
              disabled={decide.isPending || needsNote}
              title={needsNote ? 'Nhập ghi chú để trả hồ sơ' : undefined}
            >
              {decide.isPending && decide.variables?.decision === 'NEEDS_REVISION' ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileEdit className="h-4 w-4" />}
              Yêu cầu sửa
            </Button>
            <Button
              variant="destructive"
              onClick={() => run({ decision: 'REJECTED', notes })}
              disabled={decide.isPending || needsNote}
              title={needsNote ? 'Nhập lý do từ chối' : undefined}
            >
              {decide.isPending && decide.variables?.decision === 'REJECTED' ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
              Từ chối
            </Button>
          </div>
          {needsNote && <p className="text-xs text-muted-foreground">Cần ghi chú khi yêu cầu sửa hoặc từ chối.</p>}
        </div>
      </CardContent>

      <Dialog open={confirmApprove} onOpenChange={setConfirmApprove}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ký duyệt báo giá {quote.quoteId}</DialogTitle>
            <DialogDescription>
              Nội dung hồ sơ sẽ được đóng băng và ký số. Sau khi ký, Sale có thể gửi báo giá chính thức cho khách.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 rounded-md border border-border p-3 text-sm">
            <p>
              Khách hàng: <span className="font-medium">{quote.context.customerName}</span>
            </p>
            <p>
              Căn hộ: <span className="font-medium">{quote.unit.unitCode}</span>
            </p>
            {recommended && (
              <p>
                Phương án đề xuất: <span className="font-medium">{recommended.planLabel}</span> —{' '}
                <MoneyText amount={recommended.netPrice} size="sm" className="font-semibold" />
              </p>
            )}
            <p className="text-muted-foreground">Người ký: {user.fullName}</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmApprove(false)}>
              Huỷ
            </Button>
            <Button variant="success" onClick={() => run({ decision: 'APPROVED', notes })} disabled={decide.isPending}>
              {decide.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PenLine className="h-4 w-4" />} Ký duyệt
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
