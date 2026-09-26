import { Target } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import type { EvidenceBackedClaim, Quote, Scenario, ScenarioCode } from '@/api/contracts'
import { MoneyText } from '@/components/common/MoneyText'
import { DecisionBadge } from '@/components/common/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { formatPercent, formatVnd } from '@/lib/format'
import { recommendationSentence } from '@/lib/quoteRules'
import { cn } from '@/lib/utils'
import { CitationButton, ClaimText } from './Evidence'

type Metric = { label: string; value: (s: Scenario) => ReactNode; strong?: boolean }

const PRICE_ROWS: Metric[] = [
  { label: 'Giá bán sau ưu đãi (gồm VAT, KPBT)', value: (s) => <MoneyText amount={s.total_contract_price_vnd} className="font-semibold" />, strong: true },
  { label: 'Giá trước thuế', value: (s) => <MoneyText amount={s.net_price_before_tax_vnd} size="sm" /> },
  {
    label: 'Chiết khấu',
    value: (s) => (
      <span className="text-sm tabular-nums">
        {formatVnd(s.discount_vnd)} <span className="text-muted-foreground">({formatPercent(s.total_discount_rate)})</span>
      </span>
    ),
  },
  { label: 'Giá trị ưu đãi quy đổi', value: (s) => <MoneyText amount={s.benefit_value_vnd} size="sm" tone={s.benefit_value_vnd ? 'success' : 'muted'} /> },
]

const CASH_ROWS: Metric[] = [
  { label: 'Thanh toán ban đầu', value: (s) => <MoneyText amount={s.initial_payment_vnd} className="font-semibold" />, strong: true },
  { label: 'Tổng dòng tiền tự chi đến bàn giao', value: (s) => <MoneyText amount={s.total_cash_outflow_vnd} size="sm" /> },
  { label: 'Số đợt thanh toán', value: (s) => <span className="text-sm tabular-nums">{s.installments_count} đợt</span> },
]

export function RecommendationBanner({ quote }: { quote: Pick<Quote, 'recommendation' | 'scenarios'> }) {
  if (!quote.recommendation) return null
  const labelOf = (code: string) => quote.scenarios.find((s) => s.scenario_code === code)?.label ?? code
  return (
    <div className="flex gap-3 rounded-xl border border-gold/40 bg-gold/[0.06] p-4" data-testid="recommendation">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-gold/15 text-gold">
        <Target className="h-4 w-4" />
      </span>
      <p className="text-sm leading-relaxed">{recommendationSentence(quote.recommendation, labelOf)}</p>
    </div>
  )
}

/** Bảng đối đầu 3 phương án — tách "Giá bán sau ưu đãi" khỏi "Dòng tiền" (PRD §1.3.1). */
export function ScenarioComparison({
  scenarios,
  recommended,
  selected,
  onSelect,
}: {
  scenarios: Scenario[]
  recommended: ScenarioCode | null
  selected: ScenarioCode
  onSelect: (code: ScenarioCode) => void
}) {
  const group = (title: string, rows: Metric[]) => (
    <>
      <TableRow className="bg-muted/40 hover:bg-muted/40">
        <TableCell colSpan={scenarios.length + 1} className="py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </TableCell>
      </TableRow>
      {rows.map((row) => (
        <TableRow key={row.label}>
          <TableCell className={cn('text-sm', row.strong ? 'font-medium' : 'text-muted-foreground')}>{row.label}</TableCell>
          {scenarios.map((s) => (
            <TableCell key={s.scenario_code} className={cn('text-right', s.scenario_code === recommended && 'bg-gold/[0.05]')}>
              {row.value(s)}
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  )

  return (
    <Card>
      <CardContent className="overflow-x-auto p-0">
        <Table data-testid="scenario-comparison">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[34%]" />
              {scenarios.map((s) => (
                <TableHead key={s.scenario_code} className={cn('py-3 text-right align-bottom', s.scenario_code === recommended && 'bg-gold/[0.05]')}>
                  <button
                    type="button"
                    onClick={() => onSelect(s.scenario_code)}
                    className={cn('inline-flex flex-col items-end gap-1 rounded-md px-1 text-foreground', selected === s.scenario_code && 'underline decoration-primary decoration-2 underline-offset-4')}
                  >
                    {s.scenario_code === recommended && <Badge variant="gold">Đề xuất</Badge>}
                    <span className="font-semibold">{s.label}</span>
                  </button>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {group('Giá bán', PRICE_ROWS)}
            {group('Dòng tiền', CASH_ROWS)}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

function Line({ label, children, strong, detail }: { label: ReactNode; children: ReactNode; strong?: boolean; detail?: ReactNode }) {
  return (
    <div className={cn('flex items-start justify-between gap-4 py-2', strong && 'border-t border-border pt-3')}>
      <div className="min-w-0">
        <div className={cn('text-sm', strong && 'font-semibold')}>{label}</div>
        {detail}
      </div>
      <div className="shrink-0 text-right">{children}</div>
    </div>
  )
}

/** Bảng tính từng dòng (PRD §7): mỗi ưu đãi có trạng thái + trích dẫn điều khoản mở được chứng cứ. */
export function PriceBreakdown({ scenario }: { scenario: Scenario }) {
  return (
    <Tabs defaultValue="breakdown">
      <TabsList>
        <TabsTrigger value="breakdown">Bảng tính</TabsTrigger>
        <TabsTrigger value="schedule">Lịch thanh toán</TabsTrigger>
      </TabsList>
      <TabsContent value="breakdown">
        <Card>
          <CardContent className="divide-y divide-border/60 p-4" data-testid="price-breakdown">
            <Line label="Giá niêm yết trước thuế">
              <MoneyText amount={scenario.listed_price_before_tax_vnd} size="sm" />
            </Line>
            {scenario.rule_evaluations.map((ev) => (
              <Line
                key={ev.rule_code}
                label={
                  <span className="flex flex-wrap items-center gap-2">
                    <DecisionBadge status={ev.status} />
                    <span>{ev.title}</span>
                  </span>
                }
                detail={
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5">
                    <CitationButton title={ev.title} source={ev.source} ruleCode={ev.rule_code} />
                    {ev.status !== 'ELIGIBLE' && <span className="text-xs text-muted-foreground">{ev.reason}</span>}
                  </div>
                }
              >
                {ev.status === 'ELIGIBLE' && ev.effect === 'PRICE_REDUCTION' ? (
                  <span className="text-sm tabular-nums text-success">− {formatVnd(ev.amount_vnd)}</span>
                ) : ev.status === 'ELIGIBLE' && ev.effect === 'IN_KIND' ? (
                  <span className="text-right text-xs text-muted-foreground">
                    Hiện vật {formatVnd(ev.amount_vnd)}
                    <br />
                    không trừ vào giá
                  </span>
                ) : (
                  <span className="text-sm text-muted-foreground">—</span>
                )}
              </Line>
            ))}
            <Line label="Giá sau ưu đãi trước thuế" strong>
              <MoneyText amount={scenario.net_price_before_tax_vnd} size="sm" className="font-semibold" />
            </Line>
            <Line label="Thuế GTGT (10%)">
              <MoneyText amount={scenario.vat_vnd} size="sm" />
            </Line>
            <Line label="Kinh phí bảo trì (2%)">
              <MoneyText amount={scenario.kpbt_vnd} size="sm" />
            </Line>
            <Line label="Giá bán sau ưu đãi" strong>
              <MoneyText amount={scenario.total_contract_price_vnd} size="lg" />
            </Line>
            <p className="pt-2 font-mono text-[11px] text-muted-foreground">{scenario.calculation_hash}</p>
          </CardContent>
        </Card>
      </TabsContent>
      <TabsContent value="schedule">
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Đợt</TableHead>
                  <TableHead>Mốc</TableHead>
                  <TableHead className="text-right">Tỷ lệ</TableHead>
                  <TableHead className="text-right">Số tiền</TableHead>
                  <TableHead>Bên chi trả</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {scenario.payment_schedule.map((p) => (
                  <TableRow key={p.seq}>
                    <TableCell className="font-medium">{p.label}</TableCell>
                    <TableCell className="text-muted-foreground">{p.milestone}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatPercent(p.ratio)}</TableCell>
                    <TableCell className="text-right">
                      <MoneyText amount={p.amount_vnd} size="sm" />
                    </TableCell>
                    <TableCell>{p.payer === 'BANK' ? <Badge variant="info">Ngân hàng</Badge> : <Badge variant="muted">Khách hàng</Badge>}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  )
}

/** "Why not?" — ưu đãi không được áp dụng kèm căn cứ loại trừ. */
export function WhyNotList({ claims }: { claims: EvidenceBackedClaim[] }) {
  const whyNot = claims.filter((c) => c.direction === 'WHY_NOT')
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Ưu đãi không được áp dụng</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2" data-testid="why-not">
        {whyNot.length === 0 && <p className="text-sm text-muted-foreground">Không có ưu đãi nào bị loại.</p>}
        {whyNot.map((c) => (
          <div key={c.claim_id} className="space-y-1.5 rounded-md border border-border p-3">
            {c.decision_status && <DecisionBadge status={c.decision_status} />}
            <div className="min-w-0 space-y-1">
              <p className="text-sm leading-relaxed">
                <ClaimText claim={c} />
              </p>
              {c.source_coordinates[0] && <CitationButton title="Căn cứ loại trừ" source={c.source_coordinates[0]} ruleCode={c.rule_code} />}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

/** Kết quả đầy đủ của một phiên bản đã tính giá thành công. */
export function QuoteResults({ quote, claims }: { quote: Quote; claims: EvidenceBackedClaim[] }) {
  const recommended = quote.recommendation?.recommended_scenario ?? null
  const [selected, setSelected] = useState<ScenarioCode>(recommended ?? quote.scenarios[0]?.scenario_code ?? 'PA-CHUDONG')
  const scenario = quote.scenarios.find((s) => s.scenario_code === selected) ?? quote.scenarios[0]
  if (!scenario) return null
  return (
    <div className="space-y-4">
      <RecommendationBanner quote={quote} />
      <ScenarioComparison scenarios={quote.scenarios} recommended={recommended} selected={selected} onSelect={setSelected} />
      <div className="grid gap-4 xl:grid-cols-[1.35fr,1fr]">
        <div className="space-y-2">
          <p className="text-sm font-medium">{scenario.label}</p>
          <PriceBreakdown scenario={scenario} />
        </div>
        <WhyNotList claims={claims} />
      </div>
    </div>
  )
}
