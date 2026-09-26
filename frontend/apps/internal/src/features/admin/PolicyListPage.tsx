import { FileUp, Loader2, ScrollText } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ExtractRulesFields } from '@pricepolicy/api-client/contracts'
import { errorMessage } from '@pricepolicy/api-client/errors'
import { useExtractRules, usePolicies } from '@pricepolicy/api-client/hooks'
import { EmptyState, PageHeader, QueryState } from '@pricepolicy/ui/components/common/PageStates'
import { PolicyStatusBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { Input } from '@pricepolicy/ui/components/ui/input'
import { Label } from '@pricepolicy/ui/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@pricepolicy/ui/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@pricepolicy/ui/components/ui/table'
import { formatDate, todayIso } from '@pricepolicy/ui/lib/format'
import { PROJECT_LABEL } from '@pricepolicy/ui/lib/labels'
import { toast } from '@pricepolicy/ui/state/toastStore'

export function PolicyListPage() {
  const policies = usePolicies()
  const navigate = useNavigate()
  const [uploadOpen, setUploadOpen] = useState(false)
  const today = todayIso()
  return (
    <div className="space-y-6">
      <PageHeader
        title="Chính sách bán hàng"
        actions={
          <Button onClick={() => setUploadOpen(true)} data-testid="upload-policy">
            <FileUp className="h-4 w-4" /> Tải lên văn bản
          </Button>
        }
      />
      <QueryState query={policies} isEmpty={(d) => d.length === 0} empty={<EmptyState icon={ScrollText} title="Chưa có văn bản chính sách" />}>
        {(data) => (
          <div className="overflow-x-auto rounded-xl border border-border bg-card">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Văn bản</TableHead>
                  <TableHead>Dự án</TableHead>
                  <TableHead>Hiệu lực</TableHead>
                  <TableHead className="text-right">Điều khoản</TableHead>
                  <TableHead>Trạng thái</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((p) => (
                  <TableRow key={p.policy_id} className="cursor-pointer" onClick={() => navigate(`/admin/policies/${encodeURIComponent(p.policy_id)}`)}>
                    <TableCell>
                      <p className="font-medium">{p.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {p.policy_id} · {p.policy_version}
                      </p>
                    </TableCell>
                    <TableCell>{PROJECT_LABEL[p.project_id] ?? p.project_id}</TableCell>
                    <TableCell className="whitespace-nowrap text-sm">
                      {formatDate(p.effective_from)} – {formatDate(p.effective_to)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{p.rules.length}</TableCell>
                    <TableCell>
                      <PolicyStatusBadge status={p.status} expired={p.effective_to < today} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </QueryState>
      {uploadOpen && <UploadDialog onClose={() => setUploadOpen(false)} />}
    </div>
  )
}

function UploadDialog({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate()
  const extract = useExtractRules()
  const [file, setFile] = useState<File | null>(null)
  const [fields, setFields] = useState<ExtractRulesFields>({ project_id: 'THE_ZEN_PARK', title: '', policy_version: '', effective_from: '', effective_to: '' })
  const set = (k: keyof ExtractRulesFields, v: string) => setFields((f) => ({ ...f, [k]: v }))
  const valid = file && fields.title.trim() && fields.policy_version.trim() && fields.effective_from && fields.effective_to

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!file) return
    try {
      const draft = await extract.mutateAsync({ fields, file })
      toast.success('Đã trích xuất điều khoản', `${draft.rules.length} điều khoản chờ kiểm tra`)
      navigate(`/admin/policies/${encodeURIComponent(draft.policy_id)}`)
    } catch (err) {
      toast.error('Không nạp được văn bản', errorMessage(err))
    }
  }

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Tải lên văn bản chính sách</DialogTitle>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="file">Văn bản có dấu (PDF, DOCX)</Label>
            <Input id="file" type="file" accept=".pdf,.doc,.docx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="project">Dự án</Label>
            <Select value={fields.project_id} onValueChange={(v) => set('project_id', v)}>
              <SelectTrigger id="project">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(PROJECT_LABEL).map(([id, name]) => (
                  <SelectItem key={id} value={id}>
                    {name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-3 sm:grid-cols-[1fr,120px]">
            <div className="space-y-1.5">
              <Label htmlFor="title">Tên văn bản</Label>
              <Input id="title" value={fields.title} onChange={(e) => set('title', e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="version">Phiên bản</Label>
              <Input id="version" placeholder="v5.0" value={fields.policy_version} onChange={(e) => set('policy_version', e.target.value)} required />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="from">Hiệu lực từ</Label>
              <Input id="from" type="date" value={fields.effective_from} onChange={(e) => set('effective_from', e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="to">Hiệu lực đến</Label>
              <Input id="to" type="date" value={fields.effective_to} onChange={(e) => set('effective_to', e.target.value)} required />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Huỷ
            </Button>
            <Button type="submit" disabled={!valid || extract.isPending}>
              {extract.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />} Trích xuất điều khoản
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
