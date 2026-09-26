import { ArrowRight, CheckCircle2, ClipboardCheck, ShieldAlert, Timer, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuotes } from '@/api/hooks'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { EmptyState, ErrorState, LoadingState, PageHeader, StatCard } from '@/components/common/PageStates'
import { RiskFlagBadge } from '@/components/common/RiskFlagBadge'
import { WorkflowStatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { MANAGER_QUEUE_STATUSES } from '@/engine/workflow'
import { averageDecisionMinutes, enteredQueueAt, sortQueue } from '@/features/manager/queue'
import { formatRelative } from '@/lib/format'

export function ManagerDashboardPage() {
  const user = useCurrentUser()
  const quotes = useQuotes()

  if (quotes.isLoading) return <LoadingState />
  if (quotes.error) return <ErrorState error={quotes.error} onRetry={() => quotes.refetch()} />

  const all = quotes.data ?? []
  const queue = sortQueue(all.filter((q) => MANAGER_QUEUE_STATUSES.includes(q.status)))
  const decided = all.filter((q) => q.history.some((e) => e.type === 'APPROVED' || e.type === 'REJECTED' || e.type === 'REVISION_REQUESTED'))
  const avg = averageDecisionMinutes(all)

  const byOwner = new Map<string, { name: string; pending: number; approved: number; total: number }>()
  for (const q of all) {
    const row = byOwner.get(q.ownerId) ?? { name: q.ownerName, pending: 0, approved: 0, total: 0 }
    row.total += 1
    if (MANAGER_QUEUE_STATUSES.includes(q.status)) row.pending += 1
    if (q.status === 'APPROVED') row.approved += 1
    byOwner.set(q.ownerId, row)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Chào ${user.fullName}`}
        description={queue.length ? `${queue.length} hồ sơ đang chờ bạn quyết định.` : 'Không có hồ sơ nào đang chờ.'}
        actions={
          queue.length > 0 && (
            <Button asChild>
              <Link to={`/manager/approvals/${queue[0].quoteId}`}>
                Duyệt hồ sơ ưu tiên nhất <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          )
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Chờ duyệt" value={queue.filter((q) => q.status === 'READY_FOR_REVIEW').length} icon={ClipboardCheck} />
        <StatCard label="Thẩm định ngoại lệ" value={queue.filter((q) => q.status === 'ABSTAINED').length} icon={ShieldAlert} tone="danger" />
        <StatCard label="Ưu đãi chạm trần" value={queue.filter((q) => q.riskFlag.color === 'YELLOW').length} icon={TriangleAlert} tone="warning" />
        <StatCard
          label="Thời gian ra quyết định TB"
          value={avg === null ? '—' : `${avg} phút`}
          hint={`${decided.length} hồ sơ đã xử lý`}
          icon={Timer}
          tone="success"
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.5fr,1fr]">
        <Card>
          <CardHeader className="flex-row items-center justify-between pb-3">
            <CardTitle>Hàng đợi ưu tiên</CardTitle>
            <Link to="/manager/approvals" className="text-sm text-primary hover:underline">
              Mở hàng đợi
            </Link>
          </CardHeader>
          <CardContent className="space-y-2">
            {queue.length === 0 && <EmptyState icon={CheckCircle2} title="Đã xử lý hết hồ sơ" />}
            {queue.slice(0, 6).map((q) => (
              <Link
                key={q.quoteId}
                to={`/manager/approvals/${q.quoteId}`}
                className="flex items-center gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-muted/50"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium">{q.quoteId}</p>
                    <WorkflowStatusBadge status={q.status} />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {q.context.customerName} · {q.unit.unitCode} · {q.ownerName}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <RiskFlagBadge flag={q.riskFlag} className="text-xs" />
                  <p className="text-[11px] text-muted-foreground">chờ {formatRelative(enteredQueueAt(q)).replace(' trước', '')}</p>
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle>Đội kinh doanh</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Chuyên viên</TableHead>
                  <TableHead className="text-right">Hồ sơ</TableHead>
                  <TableHead className="text-right">Chờ duyệt</TableHead>
                  <TableHead className="text-right">Đã duyệt</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...byOwner.values()].map((r) => (
                  <TableRow key={r.name}>
                    <TableCell className="font-medium">{r.name}</TableCell>
                    <TableCell className="text-right tabular-nums">{r.total}</TableCell>
                    <TableCell className="text-right tabular-nums">{r.pending}</TableCell>
                    <TableCell className="text-right tabular-nums">{r.approved}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
