import { AlertOctagon, CalendarX2, FileQuestion, HelpCircle, ShieldAlert } from 'lucide-react'
import type { ComponentType } from 'react'
import type { ConflictFinding, Quote } from '@pricepolicy/api-client/contracts'
import { Alert, AlertDescription, AlertTitle } from '@pricepolicy/ui/components/ui/alert'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@pricepolicy/ui/components/ui/table'
import { formatVnd } from '@pricepolicy/ui/lib/format'
import { MISSING_FIELD_LABEL } from '@pricepolicy/ui/lib/labels'
import { stopKindOf, type StopKind } from '@pricepolicy/ui/lib/quoteRules'
import { CitationButton } from '@pricepolicy/ui/components/quote/Evidence'

const META: Record<StopKind, { title: string; variant: 'destructive' | 'warning'; icon: ComponentType; note: string }> = {
  CONFLICT: {
    title: 'Xung đột chính sách',
    variant: 'destructive',
    icon: ShieldAlert,
    note: 'Không tính giá cho tập ưu đãi này. Hồ sơ đã chuyển Quản lý thẩm định ngoại lệ.',
  },
  AMBIGUOUS: {
    title: 'Điều khoản chưa đủ căn cứ',
    variant: 'warning',
    icon: HelpCircle,
    note: 'Hệ thống không tự suy đoán mức ưu đãi. Hồ sơ đã chuyển Quản lý thẩm định.',
  },
  EXPIRED: {
    title: 'Chính sách hết hiệu lực tại ngày giao dịch',
    variant: 'destructive',
    icon: CalendarX2,
    note: 'Kiểm tra lại ngày giao dịch hoặc văn bản chính sách viện dẫn.',
  },
  NOT_FOUND: {
    title: 'Không có chính sách hiệu lực',
    variant: 'destructive',
    icon: CalendarX2,
    note: 'Không có văn bản nào của dự án bao trùm ngày giao dịch.',
  },
  NEEDS_INPUT: {
    title: 'Thiếu thông tin bắt buộc',
    variant: 'warning',
    icon: FileQuestion,
    note: 'Bổ sung thông tin rồi tạo phiên bản mới.',
  },
  CALCULATION_FAILED: {
    title: 'Kết quả tính không vượt qua kiểm tra tài chính',
    variant: 'destructive',
    icon: AlertOctagon,
    note: 'Báo giá bị chặn. Không hiển thị con số chưa được kiểm chứng.',
  },
}

const TIER_LABEL: Record<number, string> = { 1: 'Cấp 1 · Loại trừ tường minh', 2: 'Cấp 2 · Mâu thuẫn điều kiện', 3: 'Cấp 3 · Mơ hồ' }

function Finding({ finding }: { finding: ConflictFinding }) {
  return (
    <div className="rounded-md border border-current/20 bg-background/80 p-3 text-foreground" data-tier={finding.tier ?? 'none'}>
      {finding.tier && (
        <Badge variant={finding.status === 'AMBIGUOUS' ? 'warning' : 'danger'} className="mb-1.5">
          {TIER_LABEL[finding.tier]}
        </Badge>
      )}
      <p className="text-sm leading-relaxed">{finding.message}</p>
      {finding.source && <CitationButton className="mt-1.5" title="Điều khoản viện dẫn" source={finding.source} ruleCode={finding.rule_codes[0]} />}
    </div>
  )
}

/** Trạng thái dừng an toàn — khoá gửi duyệt (brief §3f). */
export function StopStatePanel({ quote }: { quote: Quote }) {
  const kind = stopKindOf(quote)
  if (!kind) return null
  const meta = META[kind]
  const Icon = meta.icon
  return (
    <Alert variant={meta.variant} data-stop={kind}>
      <Icon />
      <AlertTitle>{meta.title}</AlertTitle>
      <AlertDescription className="space-y-3">
        <p className="text-foreground/80">{meta.note}</p>
        {quote.conflict_report?.findings.map((f, i) => (
          <Finding key={i} finding={f} />
        ))}
        {kind === 'NEEDS_INPUT' && (
          <ul className="list-inside list-disc text-foreground">
            {quote.missing_fields.map((f) => (
              <li key={f}>{MISSING_FIELD_LABEL[f] ?? f}</li>
            ))}
          </ul>
        )}
        {kind === 'CALCULATION_FAILED' && quote.calculation_validation && (
          <div className="overflow-x-auto rounded-md border border-border bg-background text-foreground">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Kiểm tra</TableHead>
                  <TableHead>Trường</TableHead>
                  <TableHead className="text-right">Kỳ vọng</TableHead>
                  <TableHead className="text-right">Thực tế</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {quote.calculation_validation.errors.map((e, i) => (
                  <TableRow key={i}>
                    <TableCell>
                      <p className="font-medium">{e.message}</p>
                      <p className="font-mono text-[11px] text-muted-foreground">{e.code}</p>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{e.field}</TableCell>
                    <TableCell className="text-right tabular-nums">{e.expected_vnd !== null ? formatVnd(e.expected_vnd) : '—'}</TableCell>
                    <TableCell className="text-right tabular-nums text-destructive">{e.actual_vnd !== null ? formatVnd(e.actual_vnd) : '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </AlertDescription>
    </Alert>
  )
}
