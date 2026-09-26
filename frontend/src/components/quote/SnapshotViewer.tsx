import { ScrollArea } from '@/components/ui/scroll-area'
import type { PolicySnapshot } from '@/types/domain'

/** JSON Snapshot bất biến được đóng băng tại thời điểm Quản lý ký duyệt. */
export function SnapshotViewer({ snapshot, hash }: { snapshot: PolicySnapshot; hash: string }) {
  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-border bg-muted/40 p-3">
        <p className="text-xs font-medium text-muted-foreground">SHA-256</p>
        <p className="break-all font-mono text-xs">{hash}</p>
      </div>
      <ScrollArea className="h-[440px] rounded-lg border border-border bg-[#0b1220]">
        <pre className="whitespace-pre-wrap break-words p-4 font-mono text-[11px] leading-relaxed text-emerald-300">
          {JSON.stringify(snapshot, null, 2)}
        </pre>
      </ScrollArea>
    </div>
  )
}
