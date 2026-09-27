import { AlertTriangle, ArrowRight, CheckCircle2, PlayCircle, RotateCcw, ShieldAlert, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { QuoteDetail } from '@/components/QuoteDetail'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { DEMO_SCENARIOS, type DemoScenarioKind } from '@/data/demoScenarios'
import { useAppStore } from '@/state/appStore'

const KIND_META: Record<DemoScenarioKind, { label: string; icon: typeof CheckCircle2; badgeVariant: 'success' | 'danger' | 'warning' }> = {
  HAPPY: { label: 'Happy Path', icon: CheckCircle2, badgeVariant: 'success' },
  ABSTAIN: { label: 'Dừng an toàn', icon: ShieldAlert, badgeVariant: 'danger' },
  CALC_FAILED: { label: 'Lỗi tính toán', icon: AlertTriangle, badgeVariant: 'warning' },
  REJECTED: { label: 'Bị từ chối', icon: XCircle, badgeVariant: 'danger' },
}

export function DemoScenariosPage() {
  const runDemoScenario = useAppStore((s) => s.runDemoScenario)
  const resetDemo = useAppStore((s) => s.resetDemo)
  const quotes = useAppStore((s) => s.quotes)
  const [lastRunQuoteId, setLastRunQuoteId] = useState<string | null>(null)

  const lastRunQuote = quotes.find((q) => q.quoteId === lastRunQuoteId) ?? null

  function handleRun(key: string) {
    const quote = runDemoScenario(key)
    if (quote) setLastRunQuoteId(quote.quoteId)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="font-display text-2xl font-semibold tracking-tight sm:text-3xl">Kịch bản Demo — 1 Happy Path + 5 Failure Cases</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Diễn tập toàn bộ ranh giới quyết định của Agent chỉ bằng 1 click cho mỗi kịch bản.
          </p>
        </div>
        <Button variant="outline" onClick={() => { resetDemo(); setLastRunQuoteId(null) }}>
          <RotateCcw className="h-4 w-4" /> Đặt lại dữ liệu demo
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {DEMO_SCENARIOS.map((scenario) => {
          const meta = KIND_META[scenario.kind]
          return (
            <Card key={scenario.key}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base leading-snug">{scenario.title}</CardTitle>
                  <Badge variant={meta.badgeVariant} className="shrink-0">
                    <meta.icon className="h-3 w-3" /> {meta.label}
                  </Badge>
                </div>
                <CardDescription>{scenario.subtitle}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="text-muted-foreground">{scenario.narrative}</p>
                <p className="rounded-md bg-muted/60 p-2.5 text-xs leading-relaxed">
                  <span className="font-medium text-foreground">Kết quả mong đợi: </span>
                  {scenario.expectedOutcome}
                </p>
              </CardContent>
              <CardFooter>
                <Button className="w-full" onClick={() => handleRun(scenario.key)}>
                  <PlayCircle className="h-4 w-4" /> Chạy kịch bản này
                </Button>
              </CardFooter>
            </Card>
          )
        })}
      </div>

      {lastRunQuote && (
        <div className="space-y-3 rounded-xl border border-primary/30 bg-primary/[0.03] p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold">Kết quả kịch bản vừa chạy</p>
            <div className="flex gap-3 text-xs">
              <Link to="/manager" className="inline-flex items-center gap-1 font-medium text-primary underline underline-offset-2">
                Xem trong hàng đợi Quản lý <ArrowRight className="h-3 w-3" />
              </Link>
              <Link to="/audit" className="inline-flex items-center gap-1 font-medium text-primary underline underline-offset-2">
                Xem trong Kiểm toán <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </div>
          <QuoteDetail quote={lastRunQuote} />
        </div>
      )}
    </div>
  )
}
