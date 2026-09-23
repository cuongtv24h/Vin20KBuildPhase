import { HashGrid } from '@/components/HashGrid'
import { ScrollArea } from '@/components/ui/scroll-area'
import { buildSnapshot } from '@/engine/quoteFactory'
import type { Quote } from '@/types/domain'

export function SnapshotViewer({ quote }: { quote: Quote }) {
  const snapshot = buildSnapshot(quote)
  const displaySnapshot = { ...snapshot, snapshotHash: quote.snapshotHash ?? '(chưa được ký duyệt)' }
  const json = JSON.stringify(displaySnapshot, null, 2)

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr,auto]">
      <div className="min-w-0">
        <ScrollArea className="h-[420px] rounded-lg border border-border bg-[#0b1220]">
          <pre className="whitespace-pre-wrap break-words p-4 font-mono text-[11px] leading-relaxed text-emerald-300">
            {json}
          </pre>
        </ScrollArea>
      </div>
      {quote.snapshotHash && (
        <div className="flex shrink-0 flex-col items-center gap-2 self-start rounded-lg border border-border p-4">
          <p className="text-xs font-medium text-muted-foreground">SHA-256 Snapshot</p>
          <HashGrid hashHex={quote.snapshotHash} cell={8} />
          <p className="max-w-[180px] break-all text-center font-mono text-[10px] text-muted-foreground">
            {quote.snapshotHash}
          </p>
        </div>
      )}
    </div>
  )
}
