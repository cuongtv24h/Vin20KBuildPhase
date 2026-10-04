import { Info } from 'lucide-react'
import type { ReferencePlan } from '@pricepolicy/api-client/contracts'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { CitationButton, EvidenceProvider } from '@pricepolicy/ui/components/quote/Evidence'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { formatDateTime } from '@pricepolicy/ui/lib/format'
import { OBJECTIVE_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'

/** Watermark bất biến INV-RT-09 — phương án tham khảo không bao giờ trông như báo giá chính thức. */
export function Watermark({ text, className }: { text: string; className?: string }) {
  return (
    <div
      className={cn('rounded-md border border-dashed border-warning/60 bg-warning/10 px-3 py-1.5 text-center text-xs font-semibold uppercase tracking-[0.14em] text-warning-ink', className)}
      data-testid="watermark"
    >
      {text}
    </div>
  )
}

export function ReferencePlanView({ plan, compact = false }: { plan: ReferencePlan; compact?: boolean }) {
  return (
    <EvidenceProvider claims={plan.scenarios.flatMap((s) => s.claims)}>
      <div className="relative space-y-3 overflow-hidden rounded-xl border border-border bg-card p-4" data-testid="reference-plan">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 flex select-none items-center justify-center text-[42px] font-black uppercase tracking-widest text-foreground/[0.035] [transform:rotate(-18deg)]"
        >
          Tham khảo
        </div>
        <Watermark text={plan.watermark} />
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>Ưu tiên: {OBJECTIVE_LABEL[plan.objective]}</span>
          <span>Hết hạn {formatDateTime(plan.expires_at)}</span>
        </div>
        <div className={cn('grid gap-3', compact ? 'grid-cols-1' : 'md:grid-cols-3')}>
          {plan.scenarios.map((s) => {
            const recommended = s.scenario_code === plan.recommended_scenario
            return (
              <div
                key={s.scenario_code}
                className={cn('relative space-y-2 rounded-lg border p-3', recommended ? 'border-gold/60 bg-gold/[0.05]' : 'border-border', !s.feasible && 'opacity-70')}
                data-scenario={s.scenario_code}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-semibold leading-tight">{s.label}</p>
                  {recommended && <Badge variant="gold">Phù hợp ưu tiên</Badge>}
                  {!s.feasible && <Badge variant="muted">Vượt vốn tự có</Badge>}
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Thanh toán đợt đầu</p>
                  <MoneyText amount={s.initial_payment_vnd} className="font-semibold" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Giá bán tham khảo (gồm VAT, KPBT)</p>
                  <MoneyText amount={s.total_contract_price_vnd} size="sm" />
                </div>
                {s.infeasible_reason && <p className="text-xs text-muted-foreground">{s.infeasible_reason}</p>}
                {!compact && s.claims.length > 0 && (
                  <ul className="space-y-1 border-t border-border pt-2">
                    {s.claims.map((c) => (
                      <li key={c.claim_id} className="text-xs">
                        <span>{c.text}</span>
                        {c.source_coordinates[0] && (
                          <CitationButton className="ml-1" title={c.text} source={c.source_coordinates[0]} ruleCode={c.rule_code} />
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )
          })}
        </div>
        {!compact && (
          <ul className="space-y-0.5 text-xs text-muted-foreground">
            {plan.assumptions.map((a) => (
              <li key={a}>• {a}</li>
            ))}
          </ul>
        )}
        <p className="flex gap-1.5 text-xs leading-relaxed text-muted-foreground">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {plan.disclaimer}
        </p>
      </div>
    </EvidenceProvider>
  )
}
