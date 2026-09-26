import { ArrowRight, FilePlus2, Inbox, Phone, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { LeadDossier } from '@pricepolicy/api-client/contracts'
import { useLeads } from '@pricepolicy/api-client/hooks'
import { MoneyText } from '@pricepolicy/ui/components/common/MoneyText'
import { EmptyState, PageHeader, QueryState } from '@pricepolicy/ui/components/common/PageStates'
import { SlaCountdown } from '@pricepolicy/ui/components/common/SlaCountdown'
import { TemperatureBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { ReferencePlanView } from '@pricepolicy/ui/components/presales/ReferencePlanView'
import { Badge } from '@pricepolicy/ui/components/ui/badge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@pricepolicy/ui/components/ui/card'
import { formatDateTime, formatRelative } from '@pricepolicy/ui/lib/format'
import { DOSSIER_STATUS_LABEL, OBJECTIVE_LABEL, PROJECT_LABEL, SEGMENT_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'

const ORDER = (d: LeadDossier) => (d.status === 'CONVERTED_TO_QUOTE' ? 1 : 0)

export function LeadInboxPage() {
  const leads = useLeads()
  const [params, setParams] = useSearchParams()
  const selectedId = params.get('id')

  return (
    <div className="space-y-6">
      <PageHeader title="Hồ sơ khách từ tư vấn trực tuyến" />
      <QueryState
        query={leads}
        isEmpty={(d) => d.length === 0}
        empty={<EmptyState icon={Inbox} title="Chưa có hồ sơ khách mới" />}
      >
        {(data) => {
          const sorted = [...data].sort((a, b) => ORDER(a) - ORDER(b) || a.sla_due_at.localeCompare(b.sla_due_at))
          const selected = sorted.find((d) => d.dossier_id === selectedId) ?? sorted[0]
          return (
            <div className="grid gap-6 lg:grid-cols-[360px,1fr]">
              <ul className="space-y-2" data-testid="dossier-list">
                {sorted.map((d) => (
                  <li key={d.dossier_id}>
                    <button
                      type="button"
                      onClick={() => setParams({ id: d.dossier_id })}
                      className={cn(
                        'w-full space-y-1.5 rounded-xl border p-3 text-left transition-colors',
                        d.dossier_id === selected.dossier_id ? 'border-primary/50 bg-primary/[0.04] shadow-sm' : 'border-border bg-card hover:bg-muted/40',
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{d.customer.full_name}</span>
                        {d.status === 'CONVERTED_TO_QUOTE' ? <Badge variant="muted">{DOSSIER_STATUS_LABEL[d.status]}</Badge> : <TemperatureBadge temperature={d.temperature} />}
                      </div>
                      <p className="line-clamp-2 text-xs text-muted-foreground">{d.needs_summary}</p>
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] text-muted-foreground">{formatRelative(d.created_at)}</span>
                        {d.status !== 'CONVERTED_TO_QUOTE' && <SlaCountdown dueAt={d.sla_due_at} />}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
              <DossierDetail dossier={selected} />
            </div>
          )
        }}
      </QueryState>
    </div>
  )
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <div className="text-sm font-medium">{children ?? '—'}</div>
    </div>
  )
}

function DossierDetail({ dossier: d }: { dossier: LeadDossier }) {
  const c = d.constraints
  const converted = d.status === 'CONVERTED_TO_QUOTE'
  return (
    <div className="min-w-0 space-y-4" data-testid="dossier-detail">
      <Card>
        <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 space-y-0">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-lg">
              {d.customer.full_name} {!converted && <TemperatureBadge temperature={d.temperature} />}
            </CardTitle>
            <p className="flex flex-wrap items-center gap-x-3 text-sm text-muted-foreground">
              <a href={`tel:${d.customer.phone.replace(/\s/g, '')}`} className="inline-flex items-center gap-1 hover:text-foreground">
                <Phone className="h-3.5 w-3.5" /> {d.customer.phone}
              </a>
              <span>{d.dossier_id}</span>
              {!converted && <SlaCountdown dueAt={d.sla_due_at} />}
            </p>
          </div>
          {converted && d.converted_quote_id ? (
            <Button asChild variant="outline">
              <Link to={`/sale/quotes/${d.converted_quote_id}`}>
                {d.converted_quote_id} <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          ) : (
            <Button asChild data-testid="convert-dossier">
              <Link to={`/sale/quotes/new?dossier=${d.dossier_id}`}>
                <FilePlus2 className="h-4 w-4" /> Lập báo giá chính thức
              </Link>
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="rounded-md bg-muted/50 px-3 py-2 text-sm">{d.needs_summary}</p>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Fact label="Vốn tự có">{c.own_funds_vnd !== null ? <MoneyText amount={c.own_funds_vnd} size="sm" className="font-semibold" /> : null}</Fact>
            <Fact label="Trả góp tối đa / tháng">{c.monthly_capacity_vnd !== null ? <MoneyText amount={c.monthly_capacity_vnd} size="sm" className="font-semibold" /> : null}</Fact>
            <Fact label="Ưu tiên">{c.objective ? OBJECTIVE_LABEL[c.objective] : null}</Fact>
            <Fact label="Dự án">{c.project_id ? PROJECT_LABEL[c.project_id] : null}</Fact>
            <Fact label="Số phòng ngủ">{c.bedrooms}</Fact>
            <Fact label="Khách hàng">{c.customer_segment ? SEGMENT_LABEL[c.customer_segment] : null}</Fact>
          </div>
          <p className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-success" /> Khách đồng ý chia sẻ thông tin lúc {formatDateTime(d.consent.granted_at)} ({d.consent.consent_text_version})
          </p>
        </CardContent>
      </Card>
      {d.reference_plan ? <ReferencePlanView plan={d.reference_plan} /> : <EmptyState title="Khách chưa có phương án tham khảo" />}
    </div>
  )
}
