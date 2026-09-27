import { AlertTriangle, CheckCircle2, CircleDashed, Clock, FileEdit, ShieldAlert, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge, type BadgeProps } from '@/components/ui/badge'
import type { PolicyDecisionStatus, WorkflowStatus } from '@/types/domain'

const WORKFLOW_META: Record<WorkflowStatus, { label: string; variant: BadgeProps['variant']; icon: ReactNode }> = {
  DRAFT: { label: 'Bản nháp', variant: 'muted', icon: <CircleDashed className="h-3 w-3" /> },
  READY_FOR_REVIEW: { label: 'Chờ Quản lý duyệt', variant: 'info', icon: <Clock className="h-3 w-3" /> },
  ABSTAINED: { label: 'Dừng an toàn — Ngoại lệ', variant: 'danger', icon: <ShieldAlert className="h-3 w-3" /> },
  APPROVED: { label: 'Đã phê duyệt', variant: 'success', icon: <CheckCircle2 className="h-3 w-3" /> },
  REJECTED: { label: 'Đã từ chối', variant: 'danger', icon: <XCircle className="h-3 w-3" /> },
  NEEDS_REVISION: { label: 'Yêu cầu chỉnh sửa', variant: 'warning', icon: <FileEdit className="h-3 w-3" /> },
  CALCULATION_FAILED: { label: 'Lỗi tính toán', variant: 'danger', icon: <AlertTriangle className="h-3 w-3" /> },
}

export function WorkflowStatusBadge({ status, className }: { status: WorkflowStatus; className?: string }) {
  const meta = WORKFLOW_META[status]
  return (
    <Badge variant={meta.variant} className={className}>
      {meta.icon}
      {meta.label}
    </Badge>
  )
}

const RULE_STATUS_META: Record<PolicyDecisionStatus, { label: string; variant: BadgeProps['variant'] }> = {
  ELIGIBLE: { label: 'Đủ điều kiện', variant: 'success' },
  NOT_ELIGIBLE: { label: 'Không đủ điều kiện', variant: 'muted' },
  CONFLICT: { label: 'Xung đột / Loại trừ', variant: 'danger' },
  AMBIGUOUS: { label: 'Mơ hồ', variant: 'warning' },
  EXPIRED: { label: 'Hết hiệu lực', variant: 'danger' },
  PENDING_APPROVAL: { label: 'Chờ duyệt ngoại lệ', variant: 'warning' },
}

export function RuleStatusBadge({ status, className }: { status: PolicyDecisionStatus; className?: string }) {
  const meta = RULE_STATUS_META[status]
  return (
    <Badge variant={meta.variant} className={className}>
      {meta.label}
    </Badge>
  )
}
