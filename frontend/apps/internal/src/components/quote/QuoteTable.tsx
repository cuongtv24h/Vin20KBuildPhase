import { ShieldAlert } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import type { Quote } from '@pricepolicy/api-client/contracts'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { RiskFlagBadge } from '@pricepolicy/ui/components/common/RiskFlagBadge'
import { QuoteStatusBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@pricepolicy/ui/components/ui/table'
import { formatRelative } from '@pricepolicy/ui/lib/format'

export function QuoteTable({ quotes, hrefFor, showOwner, sodUserId }: { quotes: Quote[]; hrefFor: (q: Quote) => string; showOwner?: boolean; sodUserId?: string }) {
  const navigate = useNavigate()
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <Table data-testid="quote-table">
        <TableHeader>
          <TableRow>
            <TableHead>Hồ sơ</TableHead>
            <TableHead>Khách hàng</TableHead>
            {showOwner && <TableHead>Chuyên viên</TableHead>}
            <TableHead>Trạng thái</TableHead>
            <TableHead>Rủi ro</TableHead>
            <TableHead className="text-right">Phương án đề xuất</TableHead>
            <TableHead className="text-right">Cập nhật</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {quotes.map((q) => {
            const rec = q.scenarios.find((s) => s.scenario_code === q.recommendation?.recommended_scenario)
            return (
              <TableRow key={q.quote_id} className="cursor-pointer" onClick={() => navigate(hrefFor(q))} data-quote={q.quote_id}>
                <TableCell>
                  <p className="font-medium">{q.quote_id}</p>
                  <p className="text-xs text-muted-foreground">
                    v{q.quote_version} · {q.unit.unit_code}
                  </p>
                </TableCell>
                <TableCell>
                  {q.transaction_context.customer_name?.trim() ? (
                    q.transaction_context.customer_name
                  ) : (
                    <span className="text-muted-foreground/70" title="Hồ sơ này chưa được gắn với khách hàng trong CRM">
                      Chưa gắn khách
                    </span>
                  )}
                </TableCell>
                {showOwner && (
                  <TableCell>
                    <span className="inline-flex items-center gap-1">
                      {q.created_by.full_name}
                      {sodUserId === q.created_by.user_id && <ShieldAlert className="h-3.5 w-3.5 text-warning" aria-label="Hồ sơ do bạn lập" />}
                    </span>
                  </TableCell>
                )}
                <TableCell>
                  <QuoteStatusBadge status={q.status} />
                </TableCell>
                <TableCell>
                  <RiskFlagBadge flag={q.risk_flag} className="text-xs" />
                </TableCell>
                <TableCell className="text-right">
                  {rec ? (
                    <>
                      <MoneyText amount={rec.total_contract_price_vnd} size="sm" className="font-medium" />
                      <p className="text-xs text-muted-foreground">{rec.label}</p>
                    </>
                  ) : (
                    <span className="text-muted-foreground/70">Chưa có</span>
                  )}
                </TableCell>
                <TableCell className="text-right text-xs text-muted-foreground">{formatRelative(q.updated_at)}</TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
