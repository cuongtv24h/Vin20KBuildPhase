import { CopyPlus, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { errorMessage } from '@/api/errors'
import { useCreatePolicyDraft, usePolicies, useProjects } from '@/api/hooks'
import { ErrorState, LoadingState, PageHeader } from '@/components/common/PageStates'
import { PolicyStatusBadge } from '@/components/common/StatusBadge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { formatDate, formatDateTime, todayIso } from '@/lib/format'
import { toast } from '@/state/toastStore'

export function PolicyListPage() {
  const policies = usePolicies()
  const projects = useProjects()
  const navigate = useNavigate()
  const createDraft = useCreatePolicyDraft()
  const [open, setOpen] = useState(false)
  const [sourceId, setSourceId] = useState('')
  const today = todayIso()

  async function handleCreate() {
    try {
      const draft = await createDraft.mutateAsync(sourceId)
      toast.success('Đã tạo bản nháp', `${draft.policyId} · ${draft.version}`)
      navigate(`/admin/policies/${draft.policyId}`)
    } catch (e) {
      toast.error('Không thể tạo bản nháp', errorMessage(e))
    }
  }

  if (policies.isLoading) return <LoadingState />
  if (policies.error) return <ErrorState error={policies.error} onRetry={() => policies.refetch()} />
  const all = policies.data ?? []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Chính sách bán hàng"
        description="Phiên bản đã ban hành được giữ nguyên để tra cứu lịch sử theo ngày giao dịch."
        actions={
          <Button
            onClick={() => {
              setSourceId(all.find((p) => p.status === 'PUBLISHED')?.policyId ?? '')
              setOpen(true)
            }}
          >
            <CopyPlus className="h-4 w-4" /> Tạo phiên bản mới
          </Button>
        }
      />

      {(projects.data ?? []).map((project) => {
        const rows = all.filter((p) => p.projectId === project.projectId)
        return (
          <section key={project.projectId} className="space-y-2">
            <h2 className="font-semibold">{project.name}</h2>
            <div className="overflow-x-auto rounded-xl border border-border bg-card">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Mã chính sách</TableHead>
                    <TableHead>Tên</TableHead>
                    <TableHead>Hiệu lực</TableHead>
                    <TableHead className="text-right">Điều khoản</TableHead>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead>Ban hành</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((p) => (
                    <TableRow key={p.policyId} className="cursor-pointer" onClick={() => navigate(`/admin/policies/${p.policyId}`)}>
                      <TableCell className="whitespace-nowrap font-medium">
                        {p.policyId}
                        <span className="ml-1 text-xs text-muted-foreground">{p.version}</span>
                      </TableCell>
                      <TableCell className="min-w-[220px] text-sm">{p.title}</TableCell>
                      <TableCell className="whitespace-nowrap text-sm">
                        {formatDate(p.effectiveFrom)} – {formatDate(p.effectiveTo)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{p.rules.length}</TableCell>
                      <TableCell>
                        <PolicyStatusBadge status={p.status} expired={p.effectiveTo < today} />
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                        {p.publishedAt ? `${formatDateTime(p.publishedAt)} · ${p.publishedBy}` : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </section>
        )
      })}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Tạo phiên bản chính sách mới</DialogTitle>
            <DialogDescription>Bản nháp được sao chép toàn bộ điều khoản từ phiên bản gốc để chỉnh sửa.</DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="source-policy">Sao chép từ</Label>
            <Select value={sourceId} onValueChange={setSourceId}>
              <SelectTrigger id="source-policy">
                <SelectValue placeholder="Chọn phiên bản gốc" />
              </SelectTrigger>
              <SelectContent>
                {all
                  .filter((p) => p.status !== 'ARCHIVED')
                  .map((p) => (
                    <SelectItem key={p.policyId} value={p.policyId}>
                      {p.policyId} ({p.version})
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Huỷ
            </Button>
            <Button onClick={handleCreate} disabled={!sourceId || createDraft.isPending}>
              {createDraft.isPending && <Loader2 className="h-4 w-4 animate-spin" />} Tạo bản nháp
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
