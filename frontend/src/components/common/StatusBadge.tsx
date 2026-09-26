import { AlertTriangle, CheckCircle2, CircleDashed, Clock, FileEdit, ShieldAlert, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { Badge, type BadgeProps } from '@/components/ui/badge'
import {
  LEAD_STATUS_LABEL,
  POLICY_STATUS_LABEL,
  UNIT_STATUS_LABEL,
  WORKFLOW_STATUS_LABEL,
} from '@/lib/labels'
import type { LeadStatus, PolicyDecisionStatus, PolicyStatus, UnitStatus, WorkflowStatus } from '@/types/domain'

type Variant = BadgeProps['variant']

const WORKFLOW_META: Record<WorkflowStatus, { variant: Variant; icon: ReactNode }> = {
  DRAFT: { variant: 'muted', icon: <CircleDashed className="h-3 w-3" /> },
  READY_FOR_REVIEW: { variant: 'info', icon: <Clock className="h-3 w-3" /> },
  ABSTAINED: { variant: 'danger', icon: <ShieldAlert className="h-3 w-3" /> },
  APPROVED: { variant: 'success', icon: <CheckCircle2 className="h-3 w-3" /> },
  REJECTED: { variant: 'danger', icon: <XCircle className="h-3 w-3" /> },
  NEEDS_REVISION: { variant: 'warning', icon: <FileEdit className="h-3 w-3" /> },
  CALCULATION_FAILED: { variant: 'danger', icon: <AlertTriangle className="h-3 w-3" /> },
}

export function WorkflowStatusBadge({ status, className }: { status: WorkflowStatus; className?: string }) {
  const meta = WORKFLOW_META[status]
  return (
    <Badge variant={meta.variant} className={className} data-status={status}>
      {meta.icon}
      {WORKFLOW_STATUS_LABEL[status]}
    </Badge>
  )
}

const RULE_STATUS_META: Record<PolicyDecisionStatus, { label: string; variant: Variant }> = {
  ELIGIBLE: { label: 'Áp dụng', variant: 'success' },
  NOT_ELIGIBLE: { label: 'Không đủ điều kiện', variant: 'muted' },
  CONFLICT: { label: 'Xung đột', variant: 'danger' },
  AMBIGUOUS: { label: 'Cần thẩm định', variant: 'warning' },
  EXPIRED: { label: 'Hết hiệu lực', variant: 'danger' },
  PENDING_APPROVAL: { label: 'Chờ duyệt ngoại lệ', variant: 'warning' },
}

export function RuleStatusBadge({ status, className }: { status: PolicyDecisionStatus; className?: string }) {
  const meta = RULE_STATUS_META[status]
  return (
    <Badge variant={meta.variant} className={className} data-status={status}>
      {meta.label}
    </Badge>
  )
}

const LEAD_VARIANT: Record<LeadStatus, Variant> = {
  NEW: 'gold',
  IN_PROGRESS: 'info',
  QUOTE_SENT: 'secondary',
  CUSTOMER_ACCEPTED: 'success',
  CLOSED: 'muted',
}

export function LeadStatusBadge({ status }: { status: LeadStatus }) {
  return (
    <Badge variant={LEAD_VARIANT[status]} data-status={status}>
      {LEAD_STATUS_LABEL[status]}
    </Badge>
  )
}

const POLICY_VARIANT: Record<PolicyStatus, Variant> = {
  DRAFT: 'warning',
  PUBLISHED: 'success',
  ARCHIVED: 'muted',
}

export function PolicyStatusBadge({ status, expired }: { status: PolicyStatus; expired?: boolean }) {
  if (status === 'PUBLISHED' && expired) {
    return (
      <Badge variant="muted" data-status="EXPIRED">
        Hết hiệu lực
      </Badge>
    )
  }
  return (
    <Badge variant={POLICY_VARIANT[status]} data-status={status}>
      {POLICY_STATUS_LABEL[status]}
    </Badge>
  )
}

const UNIT_VARIANT: Record<UnitStatus, Variant> = {
  AVAILABLE: 'success',
  RESERVED: 'warning',
  SOLD: 'muted',
}

export function UnitStatusBadge({ status }: { status: UnitStatus }) {
  return (
    <Badge variant={UNIT_VARIANT[status]} data-status={status}>
      {UNIT_STATUS_LABEL[status]}
    </Badge>
  )
}
