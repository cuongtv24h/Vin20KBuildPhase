import { ArrowLeft, Ban, CheckCircle2, CircleAlert, FileUp, Loader2, Rocket, Save, ShieldCheck, XCircle } from 'lucide-react'
import { useState, type ChangeEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { PolicyRulePatch, PublishCheckReport, UpdatePolicyDraftRequest } from '@/api/contracts'
import { errorMessage } from '@/api/errors'
import { useArchivePolicy, usePolicy, usePublishPolicy, useRunPublishChecks, useUpdatePolicyDraft } from '@/api/hooks'
import { MoneyText } from '@/components/common/MoneyText'
import { ErrorState, LoadingState } from '@/components/common/PageStates'
import { PolicyStatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDate, formatDateTime, formatPercent, todayIso, truncateHash } from '@/lib/format'
import { sha256HexOfBuffer } from '@/lib/hash'
import { SEGMENT_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { toast } from '@/state/toastStore'
import type { PolicyRule, PolicyVersion } from '@/types/domain'

const KIND_LABEL: Record<PolicyRule['kind'], string> = {
  PERCENT_DISCOUNT: 'Chiết khấu %',
  GIFT: 'Quà tặng',
  BANK_SUPPORT: 'Hỗ trợ lãi suất',
  AMBIGUOUS_CLAUSE: 'Cần thẩm định',
}

export function PolicyDetailPage() {
  const { policyId } = useParams()
  const query = usePolicy(policyId)

  if (query.isLoading) return <LoadingState />
  if (query.error || !query.data) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  return <PolicyEditor key={`${query.data.policyId}-${query.data.status}`} policy={query.data} />
}

interface RuleDraft {
  discountPct?: string
  cashEquivalentVnd?: string
  interestSupportMonths?: string
}

function toRuleDraft(r: PolicyRule): RuleDraft {
  return {
    discountPct: r.discountRate !== undefined ? String(Math.round(r.discountRate * 100_000) / 1000) : undefined,
    cashEquivalentVnd: r.cashEquivalentVnd !== undefined ? String(r.cashEquivalentVnd) : undefined,
    interestSupportMonths: r.interestSupportMonths !== undefined ? String(r.interestSupportMonths) : undefined,
  }
}

function PolicyEditor({ policy }: { policy: PolicyVersion }) {
  const editable = policy.status === 'DRAFT'
  const update = useUpdatePolicyDraft()
  const runChecks = useRunPublishChecks()
  const publish = usePublishPolicy()
  const archive = useArchivePolicy()

  const [meta, setMeta] = useState({
    title: policy.title,
    version: policy.version,
    effectiveFrom: policy.effectiveFrom,
    effectiveTo: policy.effectiveTo,
    sourceDocument: policy.sourceDocument,
    sourceFileHash: policy.sourceFileHash,
  })
  const [rules, setRules] = useState<Record<string, RuleDraft>>(() => Object.fromEntries(policy.rules.map((r) => [r.ruleCode, toRuleDraft(r)])))
  const [report, setReport] = useState<PublishCheckReport | null>(null)
  const [confirmArchive, setConfirmArchive] = useState(false)
  const [hashing, setHashing] = useState(false)

  function buildPatch(): UpdatePolicyDraftRequest {
    const rulePatches: PolicyRulePatch[] = policy.rules.map((r) => {
      const d = rules[r.ruleCode]
      return {
        ruleCode: r.ruleCode,
        ...(d.discountPct !== undefined ? { discountRate: Math.round(Number(d.discountPct) * 1000) / 100_000 } : {}),
        ...(d.cashEquivalentVnd !== undefined ? { cashEquivalentVnd: Math.round(Number(d.cashEquivalentVnd)) } : {}),
        ...(d.interestSupportMonths !== undefined ? { interestSupportMonths: Math.round(Number(d.interestSupportMonths)) } : {}),
      }
    })
    return { ...meta, rules: rulePatches }
  }

  const dirty =
    editable &&
    (Object.entries(meta).some(([k, v]) => policy[k as keyof typeof meta] !== v) ||
      policy.rules.some((r) => JSON.stringify(toRuleDraft(r)) !== JSON.stringify(rules[r.ruleCode])))

  async function save(silent = false) {
    try {
      await update.mutateAsync({ policyId: policy.policyId, ...buildPatch() })
      if (!silent) toast.success('Đã lưu bản nháp', policy.policyId)
      return true
    } catch (e) {
      toast.error('Không thể lưu', errorMessage(e))
      return false
    }
  }

  async function handleCheck() {
    if (dirty && !(await save(true))) return
    try {
      setReport(await runChecks.mutateAsync(policy.policyId))
    } catch (e) {
      toast.error('Không thể chạy kiểm tra', errorMessage(e))
    }
  }

  async function handlePublish() {
    try {
      await publish.mutateAsync(policy.policyId)
      toast.success('Đã ban hành chính sách', `${policy.policyId} có hiệu lực từ ${formatDate(meta.effectiveFrom)}`)
      setReport(null)
    } catch (e) {
      toast.error('Không thể ban hành', errorMessage(e))
    }
  }

  async function handleArchive() {
    try {
      await archive.mutateAsync(policy.policyId)
      toast.success('Đã ngừng áp dụng', policy.policyId)
    } catch (e) {
      toast.error('Không thể ngừng áp dụng', errorMessage(e))
    } finally {
      setConfirmArchive(false)
    }
  }

  async function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setHashing(true)
    try {
      const hash = await sha256HexOfBuffer(await file.arrayBuffer())
      setMeta((m) => ({ ...m, sourceDocument: file.name, sourceFileHash: hash }))
    } finally {
      setHashing(false)
    }
  }

  const expired = policy.effectiveTo < todayIso()

  return (
    <div className="space-y-6">
      <Link to="/admin/policies" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Chính sách bán hàng
      </Link>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-2xl font-semibold tracking-tight">{policy.policyId}</h1>
            <PolicyStatusBadge status={policy.status} expired={expired} />
          </div>
          <p className="text-sm text-muted-foreground">
            Tạo bởi {policy.createdBy} · {formatDateTime(policy.createdAt)}
            {policy.publishedAt && ` · Ban hành ${formatDateTime(policy.publishedAt)} bởi ${policy.publishedBy}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {editable && (
            <>
              <Button variant="outline" onClick={() => save()} disabled={!dirty || update.isPending}>
                {update.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Lưu nháp
              </Button>
              <Button onClick={handleCheck} disabled={runChecks.isPending || update.isPending}>
                {runChecks.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />} Kiểm tra & ban hành
              </Button>
            </>
          )}
          {policy.status !== 'ARCHIVED' && (
            <Button variant="outline" onClick={() => setConfirmArchive(true)}>
              <Ban className="h-4 w-4" /> {editable ? 'Huỷ bản nháp' : 'Ngừng áp dụng'}
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[360px,1fr]">
        <Card className="h-fit">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Thông tin phiên bản</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="p-title">Tên chính sách</Label>
              <Input id="p-title" value={meta.title} disabled={!editable} onChange={(e) => setMeta({ ...meta, title: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="p-version">Phiên bản</Label>
              <Input id="p-version" value={meta.version} disabled={!editable} onChange={(e) => setMeta({ ...meta, version: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label htmlFor="p-from">Hiệu lực từ</Label>
                <Input id="p-from" type="date" value={meta.effectiveFrom} disabled={!editable} onChange={(e) => setMeta({ ...meta, effectiveFrom: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-to">Đến</Label>
                <Input id="p-to" type="date" value={meta.effectiveTo} disabled={!editable} onChange={(e) => setMeta({ ...meta, effectiveTo: e.target.value })} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Văn bản gốc đã đóng dấu</Label>
              {meta.sourceDocument ? (
                <div className="rounded-md border border-border p-2.5 text-sm">
                  <p className="font-medium">{meta.sourceDocument}</p>
                  <p className="font-mono text-xs text-muted-foreground">SHA-256 {truncateHash(meta.sourceFileHash, 10)}</p>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Chưa tải lên</p>
              )}
              {editable && (
                <label className="inline-flex cursor-pointer items-center gap-1.5 text-sm font-medium text-primary hover:underline">
                  {hashing ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
                  {meta.sourceDocument ? 'Thay văn bản' : 'Tải lên PDF'}
                  <input type="file" accept="application/pdf" className="hidden" onChange={handleFile} />
                </label>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Điều khoản ({policy.rules.length})</CardTitle>
          </CardHeader>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-5">Điều khoản</TableHead>
                  <TableHead>Loại</TableHead>
                  <TableHead>Giá trị</TableHead>
                  <TableHead>Điều kiện</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {policy.rules.map((r) => (
                  <TableRow key={r.ruleCode} className="align-top">
                    <TableCell className="max-w-md pl-5">
                      <p className="font-medium">{r.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {r.source.clauseTitle} · {r.ruleCode}
                      </p>
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{r.evidenceText}</p>
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-sm">{KIND_LABEL[r.kind]}</TableCell>
                    <TableCell className="min-w-[150px]">
                      <RuleValueField
                        rule={r}
                        draft={rules[r.ruleCode]}
                        editable={editable}
                        onChange={(d) => setRules((all) => ({ ...all, [r.ruleCode]: d }))}
                      />
                    </TableCell>
                    <TableCell className="min-w-[180px] text-xs text-muted-foreground">
                      <ul className="space-y-0.5">
                        {!r.isSelectable && <li>Tự động theo hồ sơ</li>}
                        {r.requiredSegments && <li>Chỉ {r.requiredSegments.map((s) => SEGMENT_LABEL[s]).join(', ')}</li>}
                        {r.minUnitsPurchased && <li>Từ {r.minUnitsPurchased} căn</li>}
                        {r.applicablePlans.length < 3 && <li>{r.applicablePlans.length} phương án</li>}
                        {r.mutualExclusion?.map((c) => (
                          <li key={c} className="text-destructive">
                            Loại trừ {c}
                          </li>
                        ))}
                        {r.conditionalConflict?.map((c) => (
                          <li key={c.ruleCode} className="text-warning">
                            Mâu thuẫn {c.ruleCode}
                          </li>
                        ))}
                      </ul>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <Dialog open={report !== null} onOpenChange={(open) => !open && setReport(null)}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Kiểm tra trước khi ban hành</DialogTitle>
            <DialogDescription>
              {policy.policyId} · hiệu lực {formatDate(meta.effectiveFrom)} – {formatDate(meta.effectiveTo)}
            </DialogDescription>
          </DialogHeader>
          <ul className="space-y-2" data-testid="publish-checks">
            {report?.checks.map((c) => (
              <li key={c.code} className="flex items-start gap-2.5 rounded-md border border-border p-2.5" data-check={c.code} data-status={c.status}>
                {c.status === 'PASS' && <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />}
                {c.status === 'WARN' && <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" />}
                {c.status === 'FAIL' && <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />}
                <div>
                  <p className="text-sm font-medium">{c.label}</p>
                  <p className="text-xs text-muted-foreground">{c.detail}</p>
                </div>
              </li>
            ))}
          </ul>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReport(null)}>
              Đóng
            </Button>
            <Button onClick={handlePublish} disabled={!report?.canPublish || publish.isPending}>
              {publish.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Rocket className="h-4 w-4" />} Ban hành
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={confirmArchive} onOpenChange={setConfirmArchive}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editable ? 'Huỷ bản nháp?' : 'Ngừng áp dụng chính sách?'}</DialogTitle>
            <DialogDescription>
              {editable
                ? 'Bản nháp sẽ chuyển sang trạng thái ngừng áp dụng và không thể ban hành.'
                : 'Báo giá có ngày giao dịch trong dải hiệu lực của chính sách này sẽ không còn được tính giá tự động.'}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmArchive(false)}>
              Quay lại
            </Button>
            <Button variant="destructive" onClick={handleArchive} disabled={archive.isPending}>
              {archive.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Xác nhận
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function RuleValueField({
  rule,
  draft,
  editable,
  onChange,
}: {
  rule: PolicyRule
  draft: RuleDraft
  editable: boolean
  onChange: (d: RuleDraft) => void
}) {
  if (rule.kind === 'AMBIGUOUS_CLAUSE') return <span className="text-xs text-warning">Không định lượng</span>

  const field =
    rule.kind === 'PERCENT_DISCOUNT' ? 'discountPct' : rule.kind === 'GIFT' ? 'cashEquivalentVnd' : 'interestSupportMonths'
  const unit = rule.kind === 'PERCENT_DISCOUNT' ? '%' : rule.kind === 'GIFT' ? 'đ' : 'tháng'

  if (!editable) {
    if (rule.kind === 'PERCENT_DISCOUNT') return <span className="font-medium tabular-nums">{formatPercent(rule.discountRate ?? 0)}</span>
    if (rule.kind === 'GIFT') return <MoneyText amount={rule.cashEquivalentVnd ?? 0} size="sm" className="font-medium" />
    return <span className="font-medium">{rule.interestSupportMonths} tháng</span>
  }

  return (
    <div className="flex items-center gap-1.5">
      <Input
        type="number"
        step={rule.kind === 'PERCENT_DISCOUNT' ? 0.1 : 1}
        min={0}
        value={draft[field] ?? ''}
        onChange={(e) => onChange({ ...draft, [field]: e.target.value })}
        className={cn('h-8 w-28 text-right tabular-nums', rule.kind === 'GIFT' && 'w-36')}
        aria-label={`Giá trị ${rule.title}`}
      />
      <span className="text-xs text-muted-foreground">{unit}</span>
    </div>
  )
}
