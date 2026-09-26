import { Check, Loader2, Pencil, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { errorMessage } from '@/api/errors'
import { useProjects, useUnits, useUpdateUnit } from '@/api/hooks'
import { MoneyText } from '@/components/common/MoneyText'
import { ErrorState, LoadingState, PageHeader } from '@/components/common/PageStates'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { UNIT_STATUS_LABEL } from '@/lib/labels'
import { toast } from '@/state/toastStore'
import type { ApartmentUnit, UnitStatus } from '@/types/domain'

export function InventoryPage() {
  const projects = useProjects()
  const units = useUnits()
  const [projectId, setProjectId] = useState('ALL')

  const rows = useMemo(
    () => (units.data ?? []).filter((u) => projectId === 'ALL' || u.projectId === projectId),
    [units.data, projectId],
  )

  return (
    <div className="space-y-6">
      <PageHeader title="Bảng hàng" description="Giá niêm yết và trạng thái căn hộ đồng bộ tới cổng khách hàng và màn hình lập báo giá." />
      <Tabs value={projectId} onValueChange={setProjectId}>
        <TabsList>
          <TabsTrigger value="ALL">Tất cả ({units.data?.length ?? 0})</TabsTrigger>
          {(projects.data ?? []).map((p) => (
            <TabsTrigger key={p.projectId} value={p.projectId}>
              {p.name} ({(units.data ?? []).filter((u) => u.projectId === p.projectId).length})
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      {units.isLoading && <LoadingState />}
      {units.error && <ErrorState error={units.error} onRetry={() => units.refetch()} />}
      {units.data && (
        <div className="overflow-x-auto rounded-xl border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mã căn</TableHead>
                <TableHead>Dự án</TableHead>
                <TableHead>Vị trí</TableHead>
                <TableHead>Loại</TableHead>
                <TableHead className="text-right">Giá niêm yết</TableHead>
                <TableHead>Trạng thái</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((u) => (
                <UnitRow key={u.unitCode} unit={u} />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}

function UnitRow({ unit }: { unit: ApartmentUnit }) {
  const update = useUpdateUnit()
  const [editing, setEditing] = useState(false)
  const [price, setPrice] = useState(String(unit.listedPrice))

  async function patch(input: { status?: UnitStatus; listedPrice?: number }) {
    try {
      await update.mutateAsync({ unitCode: unit.unitCode, ...input })
      toast.success('Đã cập nhật bảng hàng', unit.unitCode)
      setEditing(false)
    } catch (e) {
      toast.error('Không thể cập nhật', errorMessage(e))
    }
  }

  return (
    <TableRow data-unit={unit.unitCode}>
      <TableCell className="font-medium">{unit.unitCode}</TableCell>
      <TableCell className="text-sm">{unit.projectName}</TableCell>
      <TableCell className="whitespace-nowrap text-sm">
        {unit.block}, tầng {unit.floor}
      </TableCell>
      <TableCell className="whitespace-nowrap text-sm">
        {unit.bedrooms}PN · {unit.areaM2}m² · {unit.view}
      </TableCell>
      <TableCell className="text-right">
        {editing ? (
          <Input
            type="number"
            min={1}
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className="ml-auto h-8 w-40 text-right tabular-nums"
            aria-label={`Giá niêm yết ${unit.unitCode}`}
          />
        ) : (
          <MoneyText amount={unit.listedPrice} size="sm" />
        )}
      </TableCell>
      <TableCell>
        <Select value={unit.status} onValueChange={(v) => patch({ status: v as UnitStatus })} disabled={update.isPending}>
          <SelectTrigger className="h-8 w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(UNIT_STATUS_LABEL) as UnitStatus[]).map((s) => (
              <SelectItem key={s} value={s}>
                {UNIT_STATUS_LABEL[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </TableCell>
      <TableCell className="whitespace-nowrap text-right">
        {editing ? (
          <>
            <Button size="icon" variant="ghost" onClick={() => patch({ listedPrice: Math.round(Number(price)) })} disabled={update.isPending} aria-label="Lưu">
              {update.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            </Button>
            <Button
              size="icon"
              variant="ghost"
              onClick={() => {
                setEditing(false)
                setPrice(String(unit.listedPrice))
              }}
              aria-label="Huỷ"
            >
              <X className="h-4 w-4" />
            </Button>
          </>
        ) : (
          <Button size="icon" variant="ghost" onClick={() => setEditing(true)} aria-label="Sửa giá">
            <Pencil className="h-4 w-4" />
          </Button>
        )}
      </TableCell>
    </TableRow>
  )
}
