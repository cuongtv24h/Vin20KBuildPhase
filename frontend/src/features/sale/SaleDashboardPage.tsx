import { ArrowRight, CheckCircle2, Clock, FileEdit, FilePlus2, Inbox, MessageSquare, Send, Share2 } from 'lucide-react'
import type { ComponentType } from 'react'
import { Link } from 'react-router-dom'
import { useLeads, useQuotes } from '@/api/hooks'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { EmptyState, ErrorState, LoadingState, PageHeader, StatCard } from '@/components/common/PageStates'
import { QuoteTable } from '@/components/quote/QuoteTable'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatRelative } from '@/lib/format'
import type { Lead, Quote } from '@/types/domain'

interface Task {
  key: string
  icon: ComponentType<{ className?: string }>
  title: string
  detail: string
  to: string
  cta: string
  at: string
}

function buildTasks(quotes: Quote[], unassigned: Lead[]): Task[] {
  const tasks: Task[] = []
  for (const q of quotes) {
    const who = `${q.context.customerName} · ${q.unit.unitCode}`
    if (q.status === 'NEEDS_REVISION') {
      tasks.push({ key: q.quoteId, icon: FileEdit, title: 'Quản lý yêu cầu chỉnh sửa', detail: `${who} — ${q.approval?.notes ?? ''}`, to: `/sale/quotes/${q.quoteId}`, cta: 'Chỉnh sửa', at: q.updatedAt })
    } else if (q.status === 'DRAFT') {
      tasks.push({ key: q.quoteId, icon: Send, title: 'Bản nháp chưa gửi duyệt', detail: who, to: `/sale/quotes/${q.quoteId}`, cta: 'Mở hồ sơ', at: q.updatedAt })
    } else if (q.status === 'CALCULATION_FAILED') {
      tasks.push({ key: q.quoteId, icon: FileEdit, title: 'Kết quả tính toán không hợp lệ', detail: who, to: `/sale/quotes/${q.quoteId}`, cta: 'Kiểm tra', at: q.updatedAt })
    } else if (q.status === 'APPROVED' && !q.distribution) {
      tasks.push({ key: q.quoteId, icon: Share2, title: 'Đã được duyệt — chưa gửi khách', detail: who, to: `/sale/quotes/${q.quoteId}`, cta: 'Gửi khách', at: q.updatedAt })
    } else if (q.distribution?.customerResponse) {
      const r = q.distribution.customerResponse
      tasks.push({
        key: q.quoteId,
        icon: r.decision === 'ACCEPTED' ? CheckCircle2 : MessageSquare,
        title: r.decision === 'ACCEPTED' ? 'Khách đồng ý báo giá — xác nhận lịch ký cọc' : 'Khách cần tư vấn thêm',
        detail: `${who}${r.note ? ` — ${r.note}` : ''}`,
        to: `/sale/quotes/${q.quoteId}`,
        cta: 'Xem phản hồi',
        at: r.at,
      })
    }
  }
  for (const l of unassigned.slice(0, 3)) {
    tasks.push({ key: l.leadId, icon: Inbox, title: 'Yêu cầu mới chưa có người nhận', detail: `${l.fullName} · ${l.unitCode}`, to: '/sale/leads', cta: 'Tiếp nhận', at: l.createdAt })
  }
  return tasks.sort((a, b) => b.at.localeCompare(a.at))
}

export function SaleDashboardPage() {
  const user = useCurrentUser()
  const quotes = useQuotes()
  const unassigned = useLeads({ scope: 'UNASSIGNED' })

  if (quotes.isLoading || unassigned.isLoading) return <LoadingState />
  if (quotes.error) return <ErrorState error={quotes.error} onRetry={() => quotes.refetch()} />

  const all = quotes.data ?? []
  const count = (pred: (q: Quote) => boolean) => all.filter(pred).length
  const tasks = buildTasks(all, unassigned.data ?? [])

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Chào ${user.fullName}`}
        description="Những việc cần xử lý hôm nay."
        actions={
          <Button asChild>
            <Link to="/sale/quotes/new">
              <FilePlus2 className="h-4 w-4" /> Lập báo giá
            </Link>
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Yêu cầu chờ tiếp nhận" value={unassigned.data?.length ?? 0} icon={Inbox} tone="gold" />
        <StatCard label="Đang chờ Quản lý" value={count((q) => q.status === 'READY_FOR_REVIEW' || q.status === 'ABSTAINED')} icon={Clock} />
        <StatCard label="Cần chỉnh sửa" value={count((q) => q.status === 'NEEDS_REVISION' || q.status === 'CALCULATION_FAILED')} icon={FileEdit} tone="warning" />
        <StatCard label="Đã duyệt" value={count((q) => q.status === 'APPROVED')} hint={`${count((q) => q.status === 'APPROVED' && !q.distribution)} chưa gửi khách`} icon={CheckCircle2} tone="success" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr,1.4fr]">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Việc cần làm</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {tasks.length === 0 && <EmptyState title="Không có việc tồn đọng" />}
            {tasks.map((t) => (
              <Link
                key={`${t.key}-${t.title}`}
                to={t.to}
                className="flex items-start gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-muted/50"
              >
                <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <t.icon className="h-3.5 w-3.5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{t.title}</p>
                  <p className="line-clamp-2 text-xs text-muted-foreground">{t.detail}</p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="inline-flex items-center gap-1 text-xs font-medium text-primary">
                    {t.cta} <ArrowRight className="h-3 w-3" />
                  </p>
                  <p className="text-[11px] text-muted-foreground">{formatRelative(t.at)}</p>
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Hồ sơ gần đây</h2>
            <Link to="/sale/quotes" className="text-sm text-primary hover:underline">
              Xem tất cả
            </Link>
          </div>
          {all.length === 0 ? (
            <EmptyState title="Chưa có hồ sơ báo giá" />
          ) : (
            <QuoteTable quotes={all.slice(0, 6)} hrefFor={(id) => `/sale/quotes/${id}`} />
          )}
        </div>
      </div>
    </div>
  )
}
