import { ChevronRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { RiskFlagBadge } from '@/components/common/RiskFlagBadge'
import { WorkflowStatusBadge } from '@/components/common/StatusBadge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatRelative, formatVnd } from '@/lib/format'
import type { Quote } from '@/types/domain'

interface QuoteTableProps {
  quotes: Quote[]
  /** Đường dẫn chi tiết cho từng hồ sơ, ví dụ (id) => `/sale/quotes/${id}`. */
  hrefFor: (quoteId: string) => string
  showOwner?: boolean
  showRisk?: boolean
}

export function QuoteTable({ quotes, hrefFor, showOwner, showRisk }: QuoteTableProps) {
  const navigate = useNavigate()

  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Mã hồ sơ</TableHead>
            <TableHead>Khách hàng / Căn hộ</TableHead>
            {showOwner && <TableHead>Chuyên viên</TableHead>}
            {showRisk && <TableHead>Mức rủi ro</TableHead>}
            <TableHead>Trạng thái</TableHead>
            <TableHead className="text-right">Giá đề xuất</TableHead>
            <TableHead>Cập nhật</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {quotes.map((q) => {
            const recommended = q.scenarios.find((s) => s.plan === q.recommendation?.recommendedPlan)
            return (
              <TableRow
                key={q.quoteId}
                className="cursor-pointer"
                data-quote-id={q.quoteId}
                onClick={() => navigate(hrefFor(q.quoteId))}
              >
                <TableCell className="whitespace-nowrap font-medium">
                  {q.quoteId}
                  {q.version > 1 && <span className="ml-1 text-xs text-muted-foreground">v{q.version}</span>}
                </TableCell>
                <TableCell>
                  <p className="font-medium leading-tight">{q.context.customerName}</p>
                  <p className="text-xs text-muted-foreground">
                    {q.unit.unitCode} · {q.unit.projectName}
                  </p>
                </TableCell>
                {showOwner && <TableCell className="whitespace-nowrap text-sm">{q.ownerName}</TableCell>}
                {showRisk && (
                  <TableCell>
                    <RiskFlagBadge flag={q.riskFlag} />
                  </TableCell>
                )}
                <TableCell>
                  <WorkflowStatusBadge status={q.status} />
                </TableCell>
                <TableCell className="whitespace-nowrap text-right tabular-nums">
                  {recommended ? formatVnd(recommended.netPrice) : '—'}
                </TableCell>
                <TableCell className="whitespace-nowrap text-xs text-muted-foreground">{formatRelative(q.updatedAt)}</TableCell>
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
