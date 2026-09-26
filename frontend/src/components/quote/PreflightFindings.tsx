import { CalendarCheck2, ShieldAlert } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { formatDate } from '@/lib/format'
import type { ConflictFinding, ConflictTier, PolicyVersionRef, PreflightResult } from '@/types/domain'

const TIER_LABEL: Record<ConflictTier, string> = {
  1: 'Loại trừ lẫn nhau',
  2: 'Mâu thuẫn điều kiện',
  3: 'Điều khoản chưa rõ',
}

export function FindingItem({ finding }: { finding: ConflictFinding }) {
  return (
    <div className="rounded-md border border-destructive/30 bg-background/80 p-3">
      <Badge variant="danger" className="mb-1.5">
        {finding.tier ? TIER_LABEL[finding.tier] : 'Không có chính sách hiệu lực'}
      </Badge>
      <p className="text-sm leading-relaxed text-foreground">{finding.message}</p>
      {finding.source && (
        <p className="mt-1 text-xs text-muted-foreground">
          {finding.source.clauseTitle} · {finding.source.sourceDocument} · trang {finding.source.page}
        </p>
      )}
    </div>
  )
}

/** Kết quả dừng an toàn — hệ thống không tự tính giá khi có xung đột/mơ hồ/hết hiệu lực. */
export function PreflightFindings({ preflight }: { preflight: PreflightResult }) {
  return (
    <Alert variant="destructive">
      <ShieldAlert />
      <AlertTitle>Chưa thể tính giá tự động</AlertTitle>
      <AlertDescription>
        <p className="mb-3 text-foreground/80">
          {preflight.expired
            ? 'Ngày giao dịch không thuộc hiệu lực của chính sách bán hàng nào đang ban hành.'
            : 'Tập ưu đãi đã chọn có điểm cần Quản lý thẩm định trước khi phát hành báo giá.'}
        </p>
        <div className="space-y-2">
          {preflight.findings.map((finding, idx) => (
            <FindingItem key={`${finding.status}-${idx}`} finding={finding} />
          ))}
        </div>
      </AlertDescription>
    </Alert>
  )
}

export function ActivePolicyBanner({ policy }: { policy: PolicyVersionRef }) {
  return (
    <Alert variant="info">
      <CalendarCheck2 />
      <AlertTitle>{policy.title}</AlertTitle>
      <AlertDescription>
        Phiên bản {policy.version} · hiệu lực {formatDate(policy.effectiveFrom)} – {formatDate(policy.effectiveTo)}
      </AlertDescription>
    </Alert>
  )
}
