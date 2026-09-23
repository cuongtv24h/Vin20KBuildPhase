import { Award, Gift, Landmark } from 'lucide-react'
import type { ComponentType } from 'react'
import { MoneyText } from '@/components/MoneyText'
import { RuleStatusBadge } from '@/components/StatusBadge'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { formatNumber, formatPercent } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { CalculationResult } from '@/types/domain'

const PLAN_ICON: Record<CalculationResult['plan'], ComponentType<{ className?: string }>> = {
  STANDARD_PROGRESS: Landmark,
  EARLY_PAYMENT_95: Award,
  BANK_LOAN_SUPPORT: Gift,
}

interface ScenarioCardProps {
  scenario: CalculationResult
  isRecommended?: boolean
}

export function ScenarioCard({ scenario, isRecommended }: ScenarioCardProps) {
  const Icon = PLAN_ICON[scenario.plan]
  const visibleRules = scenario.ruleBreakdown

  return (
    <Card
      className={cn(
        'flex flex-col',
        isRecommended && 'border-gold/60 shadow-md ring-1 ring-gold/30',
      )}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'flex h-8 w-8 shrink-0 items-center justify-center rounded-md',
                isRecommended ? 'bg-gold/15 text-gold' : 'bg-muted text-muted-foreground',
              )}
            >
              <Icon className="h-4 w-4" />
            </span>
            <p className="font-medium leading-tight">{scenario.planLabel}</p>
          </div>
          {isRecommended && (
            <Badge variant="gold" className="shrink-0">
              Đề xuất
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-4">
        <div>
          <p className="text-xs text-muted-foreground">Giá bán sau ưu đãi (Net Price)</p>
          <MoneyText amount={scenario.netPrice} size="xl" className="block" />
          <p className="mt-0.5 text-xs text-muted-foreground">
            Tổng ưu đãi {formatPercent(scenario.totalDiscountRate)} · Giảm {formatNumber(scenario.discountAmount)} đ trên giá niêm yết
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 rounded-lg bg-muted/50 p-3">
          <div>
            <p className="text-[11px] text-muted-foreground">Thanh toán đợt 1</p>
            <MoneyText amount={scenario.initialPaymentVnd} size="lg" className="block" />
          </div>
          <div>
            <p className="text-[11px] text-muted-foreground">Dòng tiền đến bàn giao</p>
            <MoneyText amount={scenario.totalCashOutflowToHandoverVnd} size="lg" className="block" />
          </div>
          <div>
            <p className="text-[11px] text-muted-foreground">Số đợt thanh toán</p>
            <p className="text-sm font-medium tabular-nums">{scenario.installmentsCount} đợt</p>
          </div>
          <div>
            <p className="text-[11px] text-muted-foreground">Giá trị ưu đãi quy đổi</p>
            <MoneyText amount={scenario.benefitValueVnd} size="lg" className="block" tone={scenario.benefitValueVnd > 0 ? 'success' : 'muted'} />
          </div>
        </div>

        <Separator />

        <div className="flex flex-1 flex-col gap-2.5">
          <p className="text-xs font-medium text-muted-foreground">Chi tiết căn cứ áp dụng (Why / Why-not)</p>
          {visibleRules.length === 0 && (
            <p className="text-xs text-muted-foreground">Không có ưu đãi nào được xét cho phương án này.</p>
          )}
          {visibleRules.map((rule) => (
            <div key={rule.ruleCode} className="rounded-md border border-border/70 p-2.5">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium leading-snug">{rule.title}</p>
                <RuleStatusBadge status={rule.status} className="shrink-0" />
              </div>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{rule.reasonText}</p>
              <div className="mt-1.5 flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{rule.source.clauseTitle}</span>
                {rule.amountVnd > 0 && (
                  <span className="font-medium tabular-nums text-success">+{formatNumber(rule.amountVnd)} đ</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
