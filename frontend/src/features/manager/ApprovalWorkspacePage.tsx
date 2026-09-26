import { CheckCircle2, Download, FileEdit, KeyRound, Loader2, PenLine, RefreshCw, ShieldAlert, ShieldCheck, XCircle } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type { Quote } from '@/api/contracts'
import { errorMessage, isStaleVersion } from '@/api/errors'
import {
  useApproveQuote,
  useQuote,
  useQuoteAudit,
  useQuoteEvidence,
  useQuotePdf,
  useReauth,
  useRejectQuote,
  useRequestRevision,
  useRetryPdf,
} from '@/api/hooks'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { MoneyText } from '@/components/common/MoneyText'
import { ErrorState, LoadingState, QueryState } from '@/components/common/PageStates'
import { PdfStatusBadge } from '@/components/common/StatusBadge'
import { EvidenceProvider } from '@/components/quote/Evidence'
import { AuditTimeline, ClaimsPanel, ContextCard, QuoteHeader } from '@/components/quote/QuoteMeta'
import { QuoteResults } from '@/components/quote/QuoteResults'
import { StopStatePanel } from '@/components/quote/StopStatePanel'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { formatDateTime, truncateHash } from '@/lib/format'
import { managerActions, stopKindOf } from '@/lib/quoteRules'
import { toast } from '@/state/toastStore'

const REASON_TEMPLATES = ['Bổ sung sổ hộ khẩu.', 'Chỉ giữ một trong hai ưu đãi loại trừ nhau.', 'Cập nhật đúng số lượng căn khách đăng ký.', 'Điều khoản chưa đủ căn cứ, bỏ khỏi đề nghị.']

export function ApprovalWorkspacePage() {
  const { quoteId } = useParams()
  const [params, setParams] = useSearchParams()
  const version = params.get('v') ? Number(params.get('v')) : undefined
  const query = useQuote(quoteId, version)
  if (query.isLoading) return <LoadingState />
  if (!query.data) return <ErrorState error={query.error ?? new Error('Không tìm thấy hồ sơ.')} onRetry={() => query.refetch()} />
  return <Workspace quote={query.data} onVersionChange={(v) => setParams(v ? { v: String(v) } : {})} />
}

function Workspace({ quote, onVersionChange }: { quote: Quote; onVersionChange: (v: number | undefined) => void }) {
  const evidence = useQuoteEvidence(quote, quote.status !== 'ANALYZING')
  const audit = useQuoteAudit(quote.quote_id, `${quote.quote_version}:${quote.status}:${quote.pdf_status}`)
  const stop = stopKindOf(quote)
  return (
    <EvidenceProvider claims={evidence.data?.claims}>
      <div className="space-y-6">
        <QuoteHeader quote={quote} backTo="/manager/approvals" backLabel="Phê duyệt báo giá" onVersionChange={onVersionChange} />
        <div className="grid gap-6 xl:grid-cols-[1fr,360px]">
          <div className="min-w-0 space-y-6">
            {stop && <StopStatePanel quote={quote} />}
            <QueryState query={evidence} loadingLabel="Đang tải chứng cứ…">
              {(ev) => (
                <>
                  {!stop && quote.scenarios.length > 0 && <QuoteResults quote={quote} claims={ev.claims} />}
                  {ev.claims.some((c) => c.direction === 'WHY') && (
                    <Card>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-sm">Luận điểm & chứng cứ</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <ClaimsPanel claims={ev.claims} />
                      </CardContent>
                    </Card>
                  )}
                </>
              )}
            </QueryState>
          </div>
          <div className="space-y-4">
            <DecisionPanel key={`${quote.quote_id}:${quote.quote_version}:${quote.status}`} quote={quote} />
            {quote.pdf_status && <PdfCard quote={quote} />}
            <ContextCard quote={quote} />
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">Nhật ký hồ sơ</CardTitle>
              </CardHeader>
              <CardContent>
                <QueryState query={audit}>{(a) => <AuditTimeline audit={a} />}</QueryState>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </EvidenceProvider>
  )
}

function DecisionPanel({ quote }: { quote: Quote }) {
  const user = useCurrentUser()
  const navigate = useNavigate()
  const can = managerActions(quote, user.role, user.user_id)
  const reject = useRejectQuote()
  const revise = useRequestRevision()
  const [reason, setReason] = useState('')
  const [approveOpen, setApproveOpen] = useState(false)
  const rec = quote.scenarios.find((s) => s.scenario_code === quote.recommendation?.recommended_scenario)
  const busy = reject.isPending || revise.isPending

  async function decide(kind: 'reject' | 'revise') {
    try {
      await (kind === 'reject' ? reject : revise).mutateAsync({ quote, extra: { reason: reason.trim() } })
      toast.success(kind === 'reject' ? 'Đã từ chối hồ sơ' : 'Đã trả hồ sơ cho Sale', quote.quote_id)
      navigate('/manager/approvals')
    } catch (e) {
      toast.error(isStaleVersion(e) ? 'Hồ sơ đã có phiên bản mới' : 'Không lưu được quyết định', errorMessage(e))
    }
  }

  if (!can.approve && !can.reject) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Quyết định</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {can.sodViolation && <SodNotice />}
          {quote.approval ? (
            <>
              <p className="font-medium">
                {quote.approval.decision === 'APPROVED' ? 'Đã phê duyệt' : quote.approval.decision === 'REJECTED' ? 'Đã từ chối' : 'Đã yêu cầu chỉnh sửa'}
              </p>
              <p className="text-muted-foreground">
                {quote.approval.decided_by.full_name} · {formatDateTime(quote.approval.decided_at)}
              </p>
              {quote.approval.reason && <p className="rounded-md bg-muted/60 p-2">{quote.approval.reason}</p>}
              {quote.approval.signature && (
                <p className="font-mono text-[11px] text-muted-foreground" title={quote.approval.signature.signature}>
                  Ed25519 · {quote.approval.signature.key_id} · {truncateHash(quote.approval.signature.signature, 8)}
                </p>
              )}
            </>
          ) : (
            !can.sodViolation && <p className="text-muted-foreground">Hồ sơ chưa ở bước chờ duyệt.</p>
          )}
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="border-primary/30 shadow-md" data-testid="decision-panel">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm">Quyết định của bạn</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="inline-flex items-center gap-1.5 text-xs font-medium text-success" data-sod="ok">
          <ShieldCheck className="h-3.5 w-3.5" /> Tách biệt nhiệm vụ: người lập {quote.created_by.full_name}
        </p>
        {rec && (
          <div className="rounded-md bg-muted/60 p-3">
            <p className="text-xs text-muted-foreground">{rec.label}</p>
            <MoneyText amount={rec.total_contract_price_vnd} size="lg" />
          </div>
        )}
        {quote.status === 'ABSTAINED' && (
          <p className="flex gap-2 rounded-md bg-destructive/5 p-2.5 text-sm text-destructive">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" /> Không có giá tự động để phê duyệt.
          </p>
        )}
        <div className="space-y-1.5">
          <Label htmlFor="reason">Lý do (bắt buộc khi từ chối hoặc yêu cầu sửa)</Label>
          <Textarea id="reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
          <div className="flex flex-wrap gap-1.5">
            {REASON_TEMPLATES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setReason((r) => (r ? `${r} ${t}` : t))}
                className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                {t}
              </button>
            ))}
          </div>
        </div>
        <div className="grid gap-2">
          {can.approve && (
            <Button variant="success" onClick={() => setApproveOpen(true)} disabled={busy} data-testid="approve">
              <CheckCircle2 className="h-4 w-4" /> Phê duyệt
            </Button>
          )}
          <div className="grid grid-cols-2 gap-2">
            <Button variant="outline" onClick={() => decide('revise')} disabled={busy || !reason.trim()} data-testid="request-revision">
              {revise.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileEdit className="h-4 w-4" />} Yêu cầu sửa
            </Button>
            <Button variant="destructive" onClick={() => decide('reject')} disabled={busy || !reason.trim()} data-testid="reject">
              {reject.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />} Từ chối
            </Button>
          </div>
        </div>
      </CardContent>
      {approveOpen && <ApproveDialog quote={quote} onClose={() => setApproveOpen(false)} />}
    </Card>
  )
}

function SodNotice() {
  return (
    <p className="flex gap-2 rounded-md bg-warning/10 p-2.5 text-sm text-warning-foreground" data-sod="violation">
      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" /> Hồ sơ do bạn lập — cần Quản lý khác phê duyệt.
    </p>
  )
}

/** Xác nhận + re-auth (TD-4.1 §3.2). Mật khẩu chỉ nằm trong state của dialog, không log, không lưu. */
function ApproveDialog({ quote, onClose }: { quote: Quote; onClose: () => void }) {
  const navigate = useNavigate()
  const reauth = useReauth()
  const approve = useApproveQuote()
  const [password, setPassword] = useState('')
  const [note, setNote] = useState('')
  const rec = quote.scenarios.find((s) => s.scenario_code === quote.recommendation?.recommended_scenario)
  const busy = reauth.isPending || approve.isPending
  const error = reauth.error ?? approve.error

  async function handleApprove(e: FormEvent) {
    e.preventDefault()
    try {
      const grant = await reauth.mutateAsync({ password })
      await approve.mutateAsync({ quote, extra: { note: note.trim(), reauthToken: grant.reauth_token } })
      setPassword('')
      toast.success('Đã phê duyệt & ký số', quote.quote_id)
      onClose()
      navigate(`/manager/approvals/${quote.quote_id}`)
    } catch {
      setPassword('')
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <form onSubmit={handleApprove} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Ký duyệt {quote.quote_id} · v{quote.quote_version}</DialogTitle>
            <DialogDescription>Nội dung phiên bản này sẽ được đóng băng và ký Ed25519.</DialogDescription>
          </DialogHeader>
          <div className="space-y-1 rounded-md border border-border p-3 text-sm">
            <p>
              {quote.transaction_context.customer_name} · {quote.unit.unit_code}
            </p>
            {rec && (
              <p>
                {rec.label} — <MoneyText amount={rec.total_contract_price_vnd} size="sm" className="font-semibold" />
              </p>
            )}
            {quote.policy_snapshot_ref && (
              <p className="text-muted-foreground">
                {quote.policy_snapshot_ref.policy_id} · {truncateHash(quote.policy_snapshot_ref.snapshot_hash, 8)}
              </p>
            )}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="approve-note">Ghi chú</Label>
            <Input id="approve-note" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="reauth">Mật khẩu xác nhận</Label>
            <Input id="reauth" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          {error != null && <p className="text-sm text-destructive">{errorMessage(error)}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Huỷ
            </Button>
            <Button type="submit" variant="success" disabled={busy || !password} data-testid="confirm-approve">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
              <PenLine className="h-4 w-4" /> Ký duyệt
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/** PDF chỉ hiện "đã phát hành" khi worker báo PDF_ISSUED (INV-RT-05). */
function PdfCard({ quote }: { quote: Quote }) {
  const issued = quote.pdf_status === 'PDF_ISSUED'
  const pdf = useQuotePdf(quote.quote_id, issued)
  const retry = useRetryPdf()
  return (
    <Card data-testid="pdf-card">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm">Báo giá PDF</CardTitle>
        {quote.pdf_status && <PdfStatusBadge status={quote.pdf_status} />}
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {issued && pdf.data && (
          <>
            <p className="font-mono text-[11px] text-muted-foreground" title={pdf.data.pdf_sha256}>
              pdf_sha256 {truncateHash(pdf.data.pdf_sha256, 10)}
            </p>
            <Button asChild variant="outline" size="sm">
              <a href={pdf.data.download_url} target="_blank" rel="noreferrer">
                <Download className="h-4 w-4" /> Tải PDF
              </a>
            </Button>
          </>
        )}
        {issued && pdf.error != null && <p className="text-destructive">{errorMessage(pdf.error)}</p>}
        {quote.pdf_status === 'FAILED' && (
          <Button
            variant="outline"
            size="sm"
            disabled={retry.isPending}
            onClick={() => retry.mutateAsync(quote.quote_id).catch((e) => toast.error('Không thể thử lại', errorMessage(e)))}
          >
            <RefreshCw className="h-4 w-4" /> Xuất lại PDF
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
