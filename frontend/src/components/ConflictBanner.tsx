import { CalendarCheck2, ShieldAlert } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { formatDate } from '@/lib/format'
import type { PreflightResult } from '@/types/domain'

const TIER_LABEL: Record<1 | 2 | 3, string> = {
  1: 'Cấp 1 — Loại trừ tường minh',
  2: 'Cấp 2 — Xung đột điều kiện ngầm',
  3: 'Cấp 3 — Mơ hồ / thiếu căn cứ',
}

/** Banner đỏ hiển thị khi Preflight phát hiện vấn đề chặn tính toán (Safe Abstention Gate). */
export function ConflictBanner({ preflight }: { preflight: PreflightResult }) {
  return (
    <Alert variant="destructive">
      <ShieldAlert />
      <AlertTitle>Hệ thống dừng an toàn — không tự tính toán</AlertTitle>
      <AlertDescription>
        <p className="mb-3">
          {preflight.expired
            ? 'Không tìm thấy chính sách nào còn hiệu lực tại ngày giao dịch đã chọn. Hồ sơ được chuyển sang thẩm định ngoại lệ của Quản lý bán hàng.'
            : 'Hệ thống phát hiện xung đột hoặc điều khoản mơ hồ trong tập ưu đãi đã chọn. Hồ sơ được chuyển sang thẩm định ngoại lệ của Quản lý bán hàng.'}
        </p>
        <div className="space-y-2.5">
          {preflight.findings.map((finding, idx) => (
            <div key={idx} className="rounded-md border border-destructive/30 bg-background/70 p-3">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                {finding.tier && <Badge variant="danger">{TIER_LABEL[finding.tier]}</Badge>}
                {!finding.tier && <Badge variant="danger">Không có chính sách hiệu lực</Badge>}
              </div>
              <p className="text-sm leading-relaxed text-foreground">{finding.message}</p>
              {finding.source && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Nguồn: {finding.source.clauseTitle} — {finding.source.sourceDocument}
                </p>
              )}
            </div>
          ))}
        </div>
      </AlertDescription>
    </Alert>
  )
}

export function ActivePolicyBanner({
  policy,
}: {
  policy: { title: string; version: string; effectiveFrom: string; effectiveTo: string }
}) {
  return (
    <Alert variant="info">
      <CalendarCheck2 />
      <AlertTitle>Chính sách đang áp dụng (Time-Travel)</AlertTitle>
      <AlertDescription>
        <span className="font-medium text-foreground">{policy.title}</span> — phiên bản {policy.version}, hiệu lực từ{' '}
        {formatDate(policy.effectiveFrom)} đến {formatDate(policy.effectiveTo)}.
      </AlertDescription>
    </Alert>
  )
}
