import { FileSearch } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import type { EvidenceBackedClaim, SourceCoordinate } from '@pricepolicy/api-client/contracts'
import { SupportBadge } from '@pricepolicy/ui/components/common/StatusBadge'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@pricepolicy/ui/components/ui/dialog'
import { truncateHash } from '@pricepolicy/ui/lib/format'
import { CLAIM_TYPE_LABEL } from '@pricepolicy/ui/lib/labels'
import { cn } from '@pricepolicy/ui/lib/utils'
import { EvidenceContext, useOpenEvidence, type EvidenceTarget } from './evidenceContext'

export function EvidenceProvider({ claims, children }: { claims?: EvidenceBackedClaim[]; children: ReactNode }) {
  const [target, setTarget] = useState<EvidenceTarget | null>(null)
  const related = useMemo(
    () => (target?.ruleCode ? (claims ?? []).filter((c) => c.rule_code === target.ruleCode) : []),
    [claims, target],
  )
  return (
    <EvidenceContext.Provider value={setTarget}>
      {children}
      <Dialog open={target !== null} onOpenChange={(open) => !open && setTarget(null)}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>{target?.title}</DialogTitle>
            {target?.source && (
              <DialogDescription>
                {target.source.section} · {target.source.document_id} {target.source.document_version} · trang {target.source.page}
              </DialogDescription>
            )}
          </DialogHeader>
          {target?.source && <SourceBlock source={target.source} />}
          {related.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">Luận điểm dẫn chiếu</p>
              {related.map((c) => (
                <ClaimRow key={c.claim_id} claim={c} />
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </EvidenceContext.Provider>
  )
}

export function SourceBlock({ source }: { source: SourceCoordinate }) {
  return (
    <div className="space-y-3">
      <blockquote className="border-l-2 border-primary/40 bg-muted/40 py-2 pl-3 pr-2 text-sm leading-relaxed">{source.quote}</blockquote>
      <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-1 text-xs">
        <dt className="text-muted-foreground">Điều khoản</dt>
        <dd className="font-mono">{source.clause_id}</dd>
        <dt className="text-muted-foreground">Văn bản</dt>
        <dd>
          {source.document_id} · {source.document_version}
        </dd>
        <dt className="text-muted-foreground">SHA-256</dt>
        <dd className="font-mono" title={source.document_hash}>
          {truncateHash(source.document_hash, 12)}
        </dd>
      </dl>
    </div>
  )
}

/** Claim có phần vượt chứng cứ được gạch chân đỏ (F4 — PARTIALLY_SUPPORTED). */
export function ClaimText({ claim }: { claim: EvidenceBackedClaim }) {
  const fragment = claim.unsupported_fragment
  const idx = fragment ? claim.text.indexOf(fragment) : -1
  if (!fragment || idx === -1) return <>{claim.text}</>
  return (
    <>
      {claim.text.slice(0, idx)}
      <mark className="rounded-sm bg-destructive/10 px-0.5 text-destructive underline decoration-destructive decoration-wavy underline-offset-2">{fragment}</mark>
      {claim.text.slice(idx + fragment.length)}
    </>
  )
}

export function ClaimRow({ claim, onOpen }: { claim: EvidenceBackedClaim; onOpen?: () => void }) {
  return (
    <div className={cn('rounded-md border p-2.5 text-sm', claim.support_status === 'SUPPORTED' ? 'border-border' : 'border-warning/50 bg-warning/5')}>
      <div className="mb-1 flex flex-wrap items-center gap-1.5">
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{CLAIM_TYPE_LABEL[claim.claim_type]}</span>
        <SupportBadge status={claim.support_status} />
      </div>
      <p className="leading-relaxed">
        <ClaimText claim={claim} />
      </p>
      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
        {claim.source_coordinates.map((s) => (
          <span key={s.clause_id}>{s.section}</span>
        ))}
        {claim.calculation_refs.map((r) => (
          <span key={r} className="font-mono">
            {r}
          </span>
        ))}
        {onOpen && claim.source_coordinates.length > 0 && (
          <button type="button" onClick={onOpen} className="inline-flex items-center gap-1 text-primary hover:underline">
            <FileSearch className="h-3 w-3" /> Xem nguồn
          </button>
        )}
      </div>
    </div>
  )
}

/** Nút trích dẫn điều khoản — bấm mở panel chứng cứ. */
export function CitationButton({ title, source, ruleCode, className }: EvidenceTarget & { className?: string }) {
  const open = useOpenEvidence()
  if (!source) return null
  return (
    <button
      type="button"
      onClick={() => open({ title, source, ruleCode })}
      className={cn('inline-flex items-center gap-1 text-xs text-primary underline-offset-2 hover:underline', className)}
      data-clause={source.clause_id}
    >
      <FileSearch className="h-3 w-3" />
      {source.section}
    </button>
  )
}
