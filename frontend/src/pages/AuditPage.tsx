import { ChevronRight, FileJson } from 'lucide-react'
import { useMemo, useState } from 'react'
import { RiskFlagBadge } from '@/components/RiskFlagBadge'
import { SnapshotViewer } from '@/components/SnapshotViewer'
import { WorkflowStatusBadge } from '@/components/StatusBadge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDateTime, truncateHash } from '@/lib/format'
import { useAppStore } from '@/state/appStore'

export function AuditPage() {
  const quotes = useAppStore((s) => s.quotes)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const sorted = useMemo(
    () => [...quotes].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()),
    [quotes],
  )
  const selectedQuote = quotes.find((q) => q.quoteId === selectedId) ?? null

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">Kiểm toán & Snapshot Archive</h1>
        <p className="text-sm text-muted-foreground">
          Lưu vết mọi hồ sơ báo giá — kể cả bị từ chối hoặc dừng an toàn — phục vụ phục dựng căn cứ sau nhiều tháng.
        </p>
      </div>

      {sorted.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
          Chưa có hồ sơ nào được lưu vết. Tạo báo giá tại Sales Copilot hoặc chạy Kịch bản Demo.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mã báo giá</TableHead>
                <TableHead>Căn hộ</TableHead>
                <TableHead>Trạng thái</TableHead>
                <TableHead>Cờ rủi ro</TableHead>
                <TableHead>SHA-256</TableHead>
                <TableHead>Tạo lúc</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map((q) => (
                <TableRow key={q.quoteId} className="cursor-pointer" onClick={() => setSelectedId(q.quoteId)}>
                  <TableCell className="font-medium">{q.quoteId}</TableCell>
                  <TableCell>{q.unit.unitCode}</TableCell>
                  <TableCell>
                    <WorkflowStatusBadge status={q.status} />
                  </TableCell>
                  <TableCell>
                    <RiskFlagBadge flag={q.riskFlag} />
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {q.snapshotHash ? truncateHash(q.snapshotHash, 8) : '—'}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDateTime(q.createdAt)}</TableCell>
                  <TableCell>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog open={Boolean(selectedQuote)} onOpenChange={(open) => !open && setSelectedId(null)}>
        <DialogContent className="max-w-4xl">
          {selectedQuote && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <FileJson className="h-4 w-4" /> Policy Snapshot — {selectedQuote.quoteId}
                </DialogTitle>
              </DialogHeader>
              <SnapshotViewer quote={selectedQuote} />
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
