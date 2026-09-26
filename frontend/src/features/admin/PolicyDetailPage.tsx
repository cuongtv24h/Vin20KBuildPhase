import { AlertTriangle, ArrowLeft, CheckCircle2, Loader2, ShieldCheck, Stamp, XCircle } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { PolicyDocument, PolicyRule, RulesTestReport } from '@/api/contracts'
import { errorMessage } from '@/api/errors'
import { usePolicy, usePublishPolicy, useTestRules } from '@/api/hooks'
import { ErrorState, LoadingState } from '@/components/common/PageStates'
import { PolicyStatusBadge } from '@/components/common/StatusBadge'
import { CitationButton, EvidenceProvider } from '@/components/quote/Evidence'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDate, formatDateTime, formatPercent, formatVnd, truncateHash } from '@/lib/format'
import { PROJECT_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { toast } from '@/state/toastStore'

export function PolicyDetailPage() {
  const { policyId } = useParams()
  const policy = usePolicy(policyId)
  if (policy.isLoading) return <LoadingState />
  if (!policy.data) return <ErrorState error={policy.error ?? new Error('Không tìm thấy văn bản.')} onRetry={() => policy.refetch()} />
  return <PolicyDetail policy={policy.data} />
}

function value(rule: PolicyRule) {
  if (rule.kind === 'PERCENT_DISCOUNT') return formatPercent(rule.discount_rate ?? 0)
  if (rule.kind === 'GIFT') return formatVnd(rule.cash_equivalent_vnd ?? 0)
  if (rule.kind === 'BANK_SUPPORT') return `0% · ${rule.interest_support_months} tháng`
  return 'Theo quyết định riêng'
}

function PolicyDetail({ policy }: { policy: PolicyDocument }) {
  const test = useTestRules()
  const publish = usePublishPolicy()
  const [confirm, setConfirm] = useState(false)
  const report = test.data?.policy_id === policy.policy_id ? test.data : null

  async function handlePublish() {
    try {
      await publish.mutateAsync(policy.policy_id)
      toast.success('Đã ban hành', `${policy.title} · ${policy.policy_version}`)
      setConfirm(false)
    } catch (e) {
      toast.error('Không thể ban hành', errorMessage(e))
    }
  }

  return (
    <EvidenceProvider>
      <div className="space-y-6">
        <div className="space-y-3">
          <Link to="/admin/policies" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" /> Chính sách bán hàng
          </Link>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="font-display text-2xl font-semibold tracking-tight">{policy.title}</h1>
                <PolicyStatusBadge status={policy.status} />
              </div>
              <p className="text-sm text-muted-foreground">
                {policy.policy_id} · {policy.policy_version} · {PROJECT_LABEL[policy.project_id]} · {formatDate(policy.effective_from)} – {formatDate(policy.effective_to)}
              </p>
              <p className="font-mono text-xs text-muted-foreground" title={policy.document_hash}>
                {policy.source_document} · SHA-256 {truncateHash(policy.document_hash, 12)}
              </p>
            </div>
            {policy.status === 'DRAFT' && (
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => test.mutateAsync(policy.policy_id).catch((e) => toast.error('Không chạy được kiểm tra', errorMessage(e)))} disabled={test.isPending} data-testid="run-rules-test">
                  {test.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />} Kiểm tra trước ban hành
                </Button>
                <Button onClick={() => setConfirm(true)} disabled={!report?.can_publish} data-testid="publish">
                  <Stamp className="h-4 w-4" /> Ban hành
                </Button>
              </div>
            )}
          </div>
        </div>

        {report && <ReportView report={report} />}

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Điều khoản ({policy.rules.length})</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Điều khoản</TableHead>
                  <TableHead>Giá trị</TableHead>
                  <TableHead>Phương án</TableHead>
                  <TableHead>Quan hệ</TableHead>
                  <TableHead>Xác thực</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {policy.rules.map((r) => (
                  <TableRow key={r.rule_code}>
                    <TableCell>
                      <p className="font-medium">{r.title}</p>
                      <CitationButton title={r.title} source={r.source} />
                    </TableCell>
                    <TableCell className={cn('whitespace-nowrap', r.is_ambiguous && 'text-warning')}>{value(r)}</TableCell>
                    <TableCell className="text-xs">{r.applicable_scenarios.join(', ')}</TableCell>
                    <TableCell className="space-y-0.5 text-xs">
                      {r.relations.map((rel) => (
                        <div key={rel.rule_code}>
                          <Badge variant={rel.type === 'MUTUALLY_EXCLUSIVE' ? 'danger' : 'warning'} className="mr-1">
                            {rel.type === 'MUTUALLY_EXCLUSIVE' ? 'Loại trừ' : 'Mâu thuẫn ĐK'}
                          </Badge>
                          {rel.rule_code}
                        </div>
                      ))}
                    </TableCell>
                    <TableCell>
                      <Badge variant={r.validation_status === 'APPROVED_FOR_USE' ? 'success' : 'warning'}>{r.validation_status === 'APPROVED_FOR_USE' ? 'Đã duyệt dùng' : 'Chờ xác thực'}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Dialog open={confirm} onOpenChange={setConfirm}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Ban hành {policy.policy_version}</DialogTitle>
              <DialogDescription>
                Hiệu lực {formatDate(policy.effective_from)} – {formatDate(policy.effective_to)}. Toàn bộ {policy.rules.length} điều khoản chuyển sang trạng thái được dùng cho báo giá chính thức.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setConfirm(false)}>
                Huỷ
              </Button>
              <Button onClick={handlePublish} disabled={publish.isPending}>
                {publish.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Stamp className="h-4 w-4" />} Ban hành
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </EvidenceProvider>
  )
}

const CHECK_ICON = {
  PASS: <CheckCircle2 className="h-4 w-4 text-success" />,
  WARN: <AlertTriangle className="h-4 w-4 text-warning" />,
  FAIL: <XCircle className="h-4 w-4 text-destructive" />,
}

function ReportView({ report }: { report: RulesTestReport }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2" data-testid="rules-report">
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0 pb-3">
          <CardTitle className="text-sm">Kiểm tra trước ban hành</CardTitle>
          <span className="text-xs text-muted-foreground">{formatDateTime(report.checked_at)}</span>
        </CardHeader>
        <CardContent className="space-y-2">
          {report.checks.map((c) => (
            <div key={c.code} className="flex items-start gap-2 text-sm" data-check={c.code} data-status={c.status}>
              <span className="mt-0.5">{CHECK_ICON[c.status]}</span>
              <div>
                <p className="font-medium">{c.label}</p>
                <p className="text-xs text-muted-foreground">{c.detail}</p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Quét xung đột ({report.conflict_findings.length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {report.conflict_findings.map((f, i) => (
            <div key={i} className="rounded-md border border-border p-2.5 text-sm">
              <Badge variant={f.tier === 3 ? 'warning' : 'danger'} className="mb-1">
                Cấp {f.tier}
              </Badge>
              <p>{f.message}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
