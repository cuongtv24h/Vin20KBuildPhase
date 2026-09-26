import { AlertTriangle, ArrowRight, Building2, FileStack, ScrollText, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { usePolicies, useProjects, useQuotes, useUnits } from '@/api/hooks'
import { useCurrentUser } from '@/auth/useCurrentUser'
import { ErrorState, LoadingState, PageHeader, StatCard } from '@/components/common/PageStates'
import { PolicyStatusBadge } from '@/components/common/StatusBadge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { selectPolicyForDate } from '@/engine/conflictDetector'
import { formatDate, todayIso } from '@/lib/format'

const EXPIRY_WARNING_DAYS = 45

function daysBetween(fromIso: string, toIso: string): number {
  return Math.round((new Date(`${toIso}T00:00:00`).getTime() - new Date(`${fromIso}T00:00:00`).getTime()) / 86_400_000)
}

export function AdminDashboardPage() {
  const user = useCurrentUser()
  const policies = usePolicies()
  const projects = useProjects()
  const units = useUnits()
  const quotes = useQuotes()

  if (policies.isLoading || projects.isLoading || units.isLoading) return <LoadingState />
  if (policies.error) return <ErrorState error={policies.error} onRetry={() => policies.refetch()} />

  const today = todayIso()
  const allPolicies = policies.data ?? []
  const allUnits = units.data ?? []

  const projectRows = (projects.data ?? []).map((p) => {
    const active = selectPolicyForDate(allPolicies, p.projectId, today)
    const successor = active
      ? allPolicies.find((x) => x.projectId === p.projectId && x.status === 'PUBLISHED' && x.effectiveFrom > active.effectiveTo)
      : null
    const draft = allPolicies.find((x) => x.projectId === p.projectId && x.status === 'DRAFT')
    const daysLeft = active ? daysBetween(today, active.effectiveTo) : null
    return { project: p, active, successor, draft, daysLeft }
  })

  const warnings = projectRows.filter((r) => !r.active || (r.daysLeft !== null && r.daysLeft <= EXPIRY_WARNING_DAYS && !r.successor))

  return (
    <div className="space-y-6">
      <PageHeader title={`Chào ${user.fullName}`} description="Tình trạng chính sách và bảng hàng toàn hệ thống." />

      {warnings.map((w) => (
        <Alert key={w.project.projectId} variant="warning">
          <AlertTriangle />
          <AlertTitle>
            {w.active
              ? `${w.project.name}: chính sách ${w.active.version} hết hiệu lực sau ${w.daysLeft} ngày (${formatDate(w.active.effectiveTo)})`
              : `${w.project.name}: không có chính sách hiệu lực hôm nay`}
          </AlertTitle>
          <AlertDescription className="flex flex-wrap items-center justify-between gap-2 text-foreground/80">
            <span>Chưa có phiên bản kế tiếp được ban hành — báo giá sau thời điểm này sẽ bị dừng an toàn.</span>
            <Button asChild size="sm" variant="outline">
              <Link to={w.draft ? `/admin/policies/${w.draft.policyId}` : '/admin/policies'}>
                {w.draft ? `Mở bản nháp ${w.draft.version}` : 'Soạn phiên bản mới'} <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </AlertDescription>
        </Alert>
      ))}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Chính sách đang hiệu lực"
          value={projectRows.filter((r) => r.active).length}
          hint={`${projectRows.length} dự án`}
          icon={ShieldCheck}
          tone="success"
        />
        <StatCard label="Bản nháp chờ ban hành" value={allPolicies.filter((p) => p.status === 'DRAFT').length} icon={ScrollText} tone="warning" />
        <StatCard
          label="Căn đang mở bán"
          value={allUnits.filter((u) => u.status === 'AVAILABLE').length}
          hint={`${allUnits.filter((u) => u.status === 'RESERVED').length} giữ chỗ · ${allUnits.filter((u) => u.status === 'SOLD').length} đã bán`}
          icon={Building2}
        />
        <StatCard
          label="Hồ sơ báo giá"
          value={quotes.data?.length ?? '—'}
          hint={`${quotes.data?.filter((q) => q.status === 'APPROVED').length ?? 0} đã ký duyệt`}
          icon={FileStack}
          tone="gold"
        />
      </div>

      <Card>
        <CardHeader className="flex-row items-center justify-between pb-3">
          <CardTitle>Chính sách theo dự án</CardTitle>
          <Link to="/admin/policies" className="text-sm text-primary hover:underline">
            Quản lý chính sách
          </Link>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {projectRows.map((r) => (
            <div key={r.project.projectId} className="space-y-2 rounded-lg border border-border p-4">
              <p className="font-semibold">{r.project.name}</p>
              {r.active ? (
                <Link to={`/admin/policies/${r.active.policyId}`} className="flex items-center justify-between gap-2 text-sm hover:underline">
                  <span>
                    {r.active.version} · {formatDate(r.active.effectiveFrom)} – {formatDate(r.active.effectiveTo)}
                  </span>
                  <PolicyStatusBadge status={r.active.status} />
                </Link>
              ) : (
                <p className="text-sm text-destructive">Không có chính sách hiệu lực</p>
              )}
              {r.draft && (
                <Link to={`/admin/policies/${r.draft.policyId}`} className="flex items-center justify-between gap-2 text-sm text-muted-foreground hover:underline">
                  <span>
                    {r.draft.version} · từ {formatDate(r.draft.effectiveFrom)}
                  </span>
                  <PolicyStatusBadge status="DRAFT" />
                </Link>
              )}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
