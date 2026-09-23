import { ShieldCheck } from 'lucide-react'
import { HashGrid } from '@/components/HashGrid'
import { MoneyText } from '@/components/MoneyText'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { formatDate, formatDateTime } from '@/lib/format'
import type { Quote } from '@/types/domain'

export function OfficialQuotePreview({ quote }: { quote: Quote }) {
  const winning = quote.scenarios.find((s) => s.plan === quote.recommendation?.recommendedPlan) ?? quote.scenarios[0]

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 rounded-lg bg-primary px-4 py-3 text-primary-foreground">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5" />
          <div>
            <p className="text-sm font-semibold leading-tight">Báo giá chính thức</p>
            <p className="text-xs text-primary-foreground/70">{quote.quoteId} · Phiên bản v{quote.version}</p>
          </div>
        </div>
        <Badge variant="gold">Đã ký duyệt</Badge>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-xs text-muted-foreground">Căn hộ</p>
          <p className="font-medium">
            {quote.unit.unitCode} — {quote.unit.projectName}
          </p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Khách hàng</p>
          <p className="font-medium">{quote.context.customerName}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Phương án được duyệt</p>
          <p className="font-medium">{winning?.planLabel ?? '—'}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Ngày phê duyệt</p>
          <p className="font-medium">{quote.approval ? formatDateTime(quote.approval.timestamp) : '—'}</p>
        </div>
      </div>

      {winning && (
        <div className="rounded-lg border border-border p-4">
          <p className="text-xs text-muted-foreground">Giá bán sau ưu đãi (Net Price)</p>
          <MoneyText amount={winning.netPrice} size="xl" className="block" />
        </div>
      )}

      <Separator />

      <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="text-sm">
          <p className="font-medium">Xác thực điện tử</p>
          <p className="mt-1 max-w-xs text-xs leading-relaxed text-muted-foreground">
            Mã băm SHA-256 THẬT được tính bằng Web Crypto API (<code className="rounded bg-muted px-1 py-0.5">crypto.subtle.digest</code>)
            trên nội dung JSON Snapshot đã đóng băng. Bên thứ ba có thể đối soát lại bằng cách băm lại đúng nội dung
            snapshot.
          </p>
          <p className="mt-2 break-all font-mono text-[11px] text-foreground">{quote.snapshotHash}</p>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Phát hành ngày {quote.approval ? formatDate(quote.approval.timestamp) : '—'} · Người ký:{' '}
            {quote.approval?.approverName}
          </p>
        </div>
        {quote.snapshotHash && <HashGrid hashHex={quote.snapshotHash} />}
      </div>
    </div>
  )
}
