import { CheckCircle2, FileEdit, Loader2, XCircle } from 'lucide-react'
import { useMemo, useState } from 'react'
import { ApprovalQueueTable } from '@/components/ApprovalQueueTable'
import { OfficialQuotePreview } from '@/components/OfficialQuotePreview'
import { QuoteDetail } from '@/components/QuoteDetail'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { useAppStore } from '@/state/appStore'
import type { WorkflowStatus } from '@/types/domain'

const PENDING_STATUSES: WorkflowStatus[] = ['READY_FOR_REVIEW', 'ABSTAINED']

export function ManagerApprovalPage() {
  const quotes = useAppStore((s) => s.quotes)
  const approveQuote = useAppStore((s) => s.approveQuote)
  const rejectQuote = useAppStore((s) => s.rejectQuote)
  const requestRevision = useAppStore((s) => s.requestRevision)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [notes, setNotes] = useState('')
  const [approverName] = useState('Hà Nguyễn')
  const [isProcessing, setIsProcessing] = useState<'APPROVE' | 'REJECT' | 'REVISION' | null>(null)
  const [showOfficialPreview, setShowOfficialPreview] = useState(false)

  const pendingQuotes = useMemo(() => quotes.filter((q) => PENDING_STATUSES.includes(q.status)), [quotes])
  const selectedQuote = useMemo(() => quotes.find((q) => q.quoteId === selectedId) ?? null, [quotes, selectedId])

  function openQuote(quoteId: string) {
    setSelectedId(quoteId)
    setNotes('')
    setShowOfficialPreview(false)
  }

  async function handleApprove() {
    if (!selectedQuote) return
    setIsProcessing('APPROVE')
    await approveQuote(selectedQuote.quoteId, approverName, notes)
    setIsProcessing(null)
  }

  function handleReject() {
    if (!selectedQuote || notes.trim().length === 0) return
    setIsProcessing('REJECT')
    rejectQuote(selectedQuote.quoteId, approverName, notes)
    setIsProcessing(null)
  }

  function handleRequestRevision() {
    if (!selectedQuote) return
    setIsProcessing('REVISION')
    requestRevision(selectedQuote.quoteId, approverName, notes || 'Đề nghị Sale kiểm tra lại hồ sơ và trình duyệt lại.')
    setIsProcessing(null)
  }

  const canApprove = selectedQuote && (selectedQuote.status === 'READY_FOR_REVIEW' || selectedQuote.status === 'ABSTAINED')
  const canDecide = canApprove

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">Manager Approval Workspace</h1>
        <p className="text-sm text-muted-foreground">
          Cổng phê duyệt HITL — mọi báo giá chỉ được phát hành sau khi có chữ ký điện tử của Quản lý bán hàng.
        </p>
      </div>

      <Tabs defaultValue="pending">
        <TabsList>
          <TabsTrigger value="pending">Chờ xử lý ({pendingQuotes.length})</TabsTrigger>
          <TabsTrigger value="all">Tất cả ({quotes.length})</TabsTrigger>
        </TabsList>
        <TabsContent value="pending">
          <ApprovalQueueTable quotes={pendingQuotes} onSelect={openQuote} />
        </TabsContent>
        <TabsContent value="all">
          <ApprovalQueueTable quotes={quotes} onSelect={openQuote} />
        </TabsContent>
      </Tabs>

      <Dialog open={Boolean(selectedQuote)} onOpenChange={(open) => !open && setSelectedId(null)}>
        <DialogContent className="max-w-3xl">
          {selectedQuote && !showOfficialPreview && (
            <>
              <DialogHeader>
                <DialogTitle>Thẩm định hồ sơ báo giá</DialogTitle>
              </DialogHeader>
              <QuoteDetail quote={selectedQuote} />

              {selectedQuote.status === 'CALCULATION_FAILED' && (
                <p className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                  Không thể phê duyệt: kết quả tính toán chưa đạt chuẩn đối soát. Đề nghị Sale kiểm tra lại dữ liệu
                  đầu vào và tạo báo giá mới.
                </p>
              )}

              {selectedQuote.status === 'APPROVED' && (
                <Button onClick={() => setShowOfficialPreview(true)}>
                  <CheckCircle2 className="h-4 w-4" /> Xem báo giá chính thức
                </Button>
              )}

              {canDecide && (
                <div className="space-y-3 rounded-lg border border-border p-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="mgr-notes">
                      Ghi chú thẩm định {' '}
                      <span className="font-normal text-muted-foreground">(bắt buộc khi Từ chối)</span>
                    </Label>
                    <Textarea
                      id="mgr-notes"
                      placeholder="Ví dụ: Đồng ý áp dụng theo đúng quy chế chính sách v3.1 / Đề nghị bổ sung sổ hộ khẩu..."
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      rows={3}
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={handleApprove} disabled={isProcessing !== null} variant="success">
                      {isProcessing === 'APPROVE' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                      Phê duyệt
                    </Button>
                    <Button onClick={handleRequestRevision} disabled={isProcessing !== null} variant="outline">
                      <FileEdit className="h-4 w-4" /> Yêu cầu chỉnh sửa
                    </Button>
                    <Button
                      onClick={handleReject}
                      disabled={isProcessing !== null || notes.trim().length === 0}
                      variant="destructive"
                    >
                      <XCircle className="h-4 w-4" /> Từ chối
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}

          {selectedQuote && showOfficialPreview && <OfficialQuotePreview quote={selectedQuote} />}
        </DialogContent>
      </Dialog>
    </div>
  )
}
