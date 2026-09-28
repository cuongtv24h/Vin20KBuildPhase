import { AlertTriangle, CheckCircle2, CircleDashed, Clock, FileEdit, FileText, Loader2, ShieldAlert, XCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import type {
  ClaimSupportStatus,
  ComplianceStatus,
  LeadTemperature,
  PdfStatus,
  PolicyDecisionStatus,
  PolicyStatus,
  QuoteWorkflowStatus,
} from '@pricepolicy/api-client/contracts'
import { Badge, type BadgeProps } from '@pricepolicy/ui/components/ui/badge'
import {
  COMPLIANCE_LABEL,
  DECISION_STATUS_LABEL,
  PDF_STATUS_LABEL,
  POLICY_STATUS_LABEL,
  QUOTE_STATUS_LABEL,
  SUPPORT_LABEL,
  TEMPERATURE_LABEL,
} from '@pricepolicy/ui/lib/labels'

type Variant = BadgeProps['variant']
const icon = (Icon: typeof Clock, spin = false) => <Icon className={spin ? 'h-3 w-3 animate-spin' : 'h-3 w-3'} />

const QUOTE_META: Record<QuoteWorkflowStatus, { variant: Variant; icon: ReactNode }> = {
  DRAFT: { variant: 'muted', icon: icon(CircleDashed) },
  ANALYZING: { variant: 'info', icon: icon(Loader2, true) },
  NEEDS_INPUT: { variant: 'warning', icon: icon(FileEdit) },
  READY_FOR_REVIEW: { variant: 'info', icon: icon(Clock) },
  NEEDS_REVISION: { variant: 'warning', icon: icon(FileEdit) },
  APPROVED: { variant: 'success', icon: icon(CheckCircle2) },
  REJECTED: { variant: 'danger', icon: icon(XCircle) },
  ABSTAINED: { variant: 'danger', icon: icon(ShieldAlert) },
  BLOCKED: { variant: 'danger', icon: icon(ShieldAlert) },
  CALCULATION_FAILED: { variant: 'danger', icon: icon(AlertTriangle) },
  SUPERSEDED: { variant: 'muted', icon: icon(CircleDashed) },
  CLOSED: { variant: 'muted', icon: icon(CheckCircle2) },
  REVOKED: { variant: 'danger', icon: icon(XCircle) },
}

export function QuoteStatusBadge({ status, className }: { status: QuoteWorkflowStatus; className?: string }) {
  const meta = QUOTE_META[status]
  return (
    <Badge variant={meta.variant} className={className} data-status={status}>
      {meta.icon}
      {QUOTE_STATUS_LABEL[status]}
    </Badge>
  )
}

const PDF_VARIANT: Record<PdfStatus, Variant> = {
  PENDING: 'muted',
  GENERATING: 'info',
  PDF_ISSUED: 'success',
  FAILED: 'danger',
  RETRYING: 'warning',
  MANUAL_INTERVENTION: 'danger',
}

export function PdfStatusBadge({ status }: { status: PdfStatus }) {
  const busy = status === 'PENDING' || status === 'GENERATING' || status === 'RETRYING'
  return (
    <Badge variant={PDF_VARIANT[status]} data-status={status}>
      {busy ? icon(Loader2, true) : icon(FileText)}
      {PDF_STATUS_LABEL[status]}
    </Badge>
  )
}

const DECISION_VARIANT: Record<PolicyDecisionStatus, Variant> = {
  ELIGIBLE: 'success',
  NOT_ELIGIBLE: 'muted',
  CONFLICT: 'danger',
  AMBIGUOUS: 'warning',
  EXPIRED: 'danger',
  PENDING_APPROVAL: 'warning',
}

export function DecisionBadge({ status, className }: { status: PolicyDecisionStatus; className?: string }) {
  return (
    <Badge variant={DECISION_VARIANT[status]} className={className} data-status={status}>
      {DECISION_STATUS_LABEL[status]}
    </Badge>
  )
}

const COMPLIANCE_VARIANT: Record<ComplianceStatus, Variant> = {
  SUPPORTED: 'success',
  CONDITIONAL: 'warning',
  UNSUPPORTED: 'danger',
  PROHIBITED: 'danger',
}

export function ComplianceBadge({ status }: { status: ComplianceStatus }) {
  return (
    <Badge variant={COMPLIANCE_VARIANT[status]} data-status={status}>
      {COMPLIANCE_LABEL[status]}
    </Badge>
  )
}

const SUPPORT_VARIANT: Record<ClaimSupportStatus, Variant> = {
  SUPPORTED: 'success',
  PARTIALLY_SUPPORTED: 'warning',
  UNSUPPORTED: 'danger',
  CONTRADICTED: 'danger',
}

export function SupportBadge({ status }: { status: ClaimSupportStatus }) {
  return (
    <Badge variant={SUPPORT_VARIANT[status]} data-status={status}>
      {SUPPORT_LABEL[status]}
    </Badge>
  )
}

const TEMP_VARIANT: Record<LeadTemperature, Variant> = { HOT: 'danger', WARM: 'gold', COLD: 'muted' }

export function TemperatureBadge({ temperature }: { temperature: LeadTemperature }) {
  return (
    <Badge variant={TEMP_VARIANT[temperature]} data-temperature={temperature}>
      {TEMPERATURE_LABEL[temperature]}
    </Badge>
  )
}

const POLICY_VARIANT: Record<PolicyStatus, Variant> = { DRAFT: 'warning', PUBLISHED: 'success', ARCHIVED: 'muted' }

export function PolicyStatusBadge({ status, expired }: { status: PolicyStatus; expired?: boolean }) {
  if (status === 'PUBLISHED' && expired) return <Badge variant="muted">Hết hiệu lực</Badge>
  return (
    <Badge variant={POLICY_VARIANT[status]} data-status={status}>
      {POLICY_STATUS_LABEL[status]}
    </Badge>
  )
}
