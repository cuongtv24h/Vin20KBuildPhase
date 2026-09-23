import { ChevronRight } from 'lucide-react'
import { RiskFlagBadge } from '@/components/RiskFlagBadge'
import { WorkflowStatusBadge } from '@/components/StatusBadge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDateTime, formatVnd } from '@/lib/format'
import type { Quote } from '@/types/domain'

interface ApprovalQueueTableProps {
  quotes: Quote[]
  onSelect: (quoteId: string) => void
}

export function ApprovalQueueTable({ quotes, onSelect }: ApprovalQueueTableProps) {
  if (quotes.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
        Chưa có hồ sơ nào trong hàng đợi. Tạo báo giá tại Sales Copilot hoặc chạy Kịch bản Demo.
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Mã báo giá</TableHead>
            <TableHead>Căn hộ / Khách hàng</TableHead>
            <TableHead>Cờ rủi ro</TableHead>
            <TableHead>Trạng thái</TableHead>
            <TableHead className="text-right">Giá đề xuất</TableHead>
            <TableHead>Cập nhật</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {quotes.map((q) => {
            const recommendedScenario = q.scenarios.find((s) => s.plan === q.recommendation?.recommendedPlan)
            return (
              <TableRow key={q.quoteId} className="cursor-pointer" onClick={() => onSelect(q.quoteId)}>
                <TableCell className="font-medium">{q.quoteId}</TableCell>
                <TableCell>
                  <p className="font-medium leading-tight">{q.unit.unitCode}</p>
                  <p className="text-xs text-muted-foreground">{q.context.customerName}</p>
                </TableCell>
                <TableCell>
                  <RiskFlagBadge flag={q.riskFlag} />
                </TableCell>
                <TableCell>
                  <WorkflowStatusBadge status={q.status} />
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {recommendedScenario ? formatVnd(recommendedScenario.netPrice) : '—'}
                </TableCell>
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatDateTime(q.updatedAt)}</TableCell>
                <TableCell>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
