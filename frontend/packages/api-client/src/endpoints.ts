/**
 * Danh bạ endpoint — nguồn sự thật duy nhất về method + path mà frontend gọi.
 * `source`:
 *   TD-4.4    có trong danh sách 29 endpoint (CodeBaseIndex §4.1–4.4); đường dẫn chi tiết của
 *             nhóm pre-sales được suy luận từ "6 endpoint Pre-Sales sessions" — cần TechLead xác nhận.
 *   PROPOSED  UI cần nhưng chưa có trong TD-4.4 → danh sách đề xuất bổ sung (API_INTEGRATION.md §3).
 * MSW dùng chính bảng này để đăng ký handler; test `endpoints.test.ts` bảo đảm mock phủ đủ.
 */
import type { UserRole } from './contracts'

export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
export type EndpointSource = 'TD-4.4' | 'PROPOSED'
export type EndpointAuth = 'public' | 'staff' | readonly UserRole[]

export interface EndpointDef {
  method: HttpMethod
  path: string
  source: EndpointSource
  auth: EndpointAuth
}

const def = <const T extends EndpointDef>(d: T) => d

export const ENDPOINTS = {
  // Auth
  authLogin: def({ method: 'POST', path: '/auth/login', source: 'PROPOSED', auth: 'public' }),
  authLogout: def({ method: 'POST', path: '/auth/logout', source: 'PROPOSED', auth: 'staff' }),
  authReauth: def({ method: 'POST', path: '/auth/reauth', source: 'PROPOSED', auth: ['MANAGER'] }),

  // Admin CP — Quản trị User & Khởi tạo ban đầu
  adminSetupStatus: def({ method: 'GET', path: '/admin/setup-status', source: 'PROPOSED', auth: 'public' }),
  adminSetup: def({ method: 'POST', path: '/admin/setup', source: 'PROPOSED', auth: 'public' }),
  adminUsersList: def({ method: 'GET', path: '/admin/users', source: 'PROPOSED', auth: ['ADMIN'] }),
  adminUserCreate: def({ method: 'POST', path: '/admin/users', source: 'PROPOSED', auth: ['ADMIN'] }),
  adminUserUpdate: def({ method: 'PUT', path: '/admin/users/{user_id}', source: 'PROPOSED', auth: ['ADMIN'] }),
  adminUserDelete: def({ method: 'DELETE', path: '/admin/users/{user_id}', source: 'PROPOSED', auth: ['ADMIN'] }),

  // Tham chiếu (read-only)
  publicProjects: def({ method: 'GET', path: '/public/projects', source: 'PROPOSED', auth: 'public' }),
  units: def({ method: 'GET', path: '/units', source: 'PROPOSED', auth: 'public' }),
  policyList: def({ method: 'GET', path: '/policies', source: 'PROPOSED', auth: 'staff' }),
  policyActive: def({ method: 'GET', path: '/policies/active', source: 'PROPOSED', auth: 'staff' }),
  policyDetail: def({ method: 'GET', path: '/policies/{policy_id}', source: 'PROPOSED', auth: 'staff' }),

  // Quotes — C-01
  quoteCreate: def({ method: 'POST', path: '/quotes', source: 'TD-4.4', auth: ['SALE'] }),
  quoteList: def({ method: 'GET', path: '/quotes', source: 'PROPOSED', auth: 'staff' }),
  quoteDetail: def({ method: 'GET', path: '/quotes/{quote_id}', source: 'TD-4.4', auth: 'staff' }),
  /** TD-4.1 §3.1 ghi `/stream`, CodeBaseIndex ghi `/events` — client ưu tiên `stream_url` server trả về. */
  quoteEvents: def({ method: 'GET', path: '/quotes/{quote_id}/events', source: 'TD-4.4', auth: 'staff' }),
  quoteEvidence: def({ method: 'GET', path: '/quotes/{quote_id}/evidence', source: 'TD-4.4', auth: 'staff' }),
  quoteAudit: def({ method: 'GET', path: '/quotes/{quote_id}/audit', source: 'TD-4.4', auth: 'staff' }),
  quotePdf: def({ method: 'GET', path: '/quotes/{quote_id}/pdf', source: 'TD-4.4', auth: 'staff' }),
  quoteApprove: def({ method: 'POST', path: '/quotes/{quote_id}/approve', source: 'TD-4.4', auth: ['MANAGER'] }),
  quoteReject: def({ method: 'POST', path: '/quotes/{quote_id}/reject', source: 'TD-4.4', auth: ['MANAGER'] }),
  quoteRevision: def({ method: 'POST', path: '/quotes/{quote_id}/revision', source: 'TD-4.4', auth: ['MANAGER'] }),
  quotePdfRetry: def({ method: 'POST', path: '/quotes/{quote_id}/pdf-retry', source: 'TD-4.4', auth: ['MANAGER'] }),
  quoteSubmit: def({ method: 'POST', path: '/quotes/{quote_id}/submit', source: 'PROPOSED', auth: ['SALE'] }),
  quoteNewVersion: def({ method: 'POST', path: '/quotes/{quote_id}/versions', source: 'PROPOSED', auth: ['SALE'] }),

  // Lead Dossier — C-10
  leadList: def({ method: 'GET', path: '/leads', source: 'TD-4.4', auth: ['SALE'] }),
  leadGet: def({ method: 'GET', path: '/leads/{dossier_id}', source: 'PROPOSED', auth: ['SALE'] }),
  leadCreate: def({ method: 'POST', path: '/leads', source: 'PROPOSED', auth: ['SALE'] }),
  leadUpdate: def({ method: 'PUT', path: '/leads/{dossier_id}', source: 'PROPOSED', auth: ['SALE'] }),
  leadDelete: def({ method: 'DELETE', path: '/leads/{dossier_id}', source: 'PROPOSED', auth: ['SALE'] }),
  leadConvert: def({ method: 'POST', path: '/leads/{dossier_id}/convert-to-quote', source: 'TD-4.4', auth: ['SALE'] }),

  // Pre-Sales — C-09 (public)
  preSalesCreate: def({ method: 'POST', path: '/pre-sales/sessions', source: 'TD-4.4', auth: 'public' }),
  preSalesGet: def({ method: 'GET', path: '/pre-sales/sessions/{session_id}', source: 'TD-4.4', auth: 'public' }),
  preSalesMessage: def({ method: 'POST', path: '/pre-sales/sessions/{session_id}/messages', source: 'TD-4.4', auth: 'public' }),
  preSalesConfirm: def({ method: 'POST', path: '/pre-sales/sessions/{session_id}/constraints/confirm', source: 'TD-4.4', auth: 'public' }),
  preSalesPlan: def({ method: 'POST', path: '/pre-sales/sessions/{session_id}/plan', source: 'TD-4.4', auth: 'public' }),
  preSalesHandoff: def({ method: 'POST', path: '/pre-sales/sessions/{session_id}/handoff', source: 'TD-4.4', auth: 'public' }),
  /** SSE — sự kiện PRE_SALES_PLAN_READY (D3-1). */
  preSalesEvents: def({ method: 'GET', path: '/pre-sales/sessions/{session_id}/events', source: 'PROPOSED', auth: 'public' }),

  // Compliance — C-11 / F8
  complianceCheck: def({ method: 'POST', path: '/compliance/check-message', source: 'TD-4.4', auth: ['SALE'] }),
  complianceDraft: def({ method: 'POST', path: '/compliance/draft-message', source: 'PROPOSED', auth: ['SALE'] }),
  messageSend: def({ method: 'POST', path: '/messages/send', source: 'TD-4.4', auth: ['SALE'] }),

  // Policy Admin — C-03 / F9
  policyExtract: def({ method: 'POST', path: '/policies/extract-rules', source: 'TD-4.4', auth: ['POLICY_ADMIN'] }),
  policyRulesTest: def({ method: 'POST', path: '/policies/{policy_id}/rules/test', source: 'TD-4.4', auth: ['POLICY_ADMIN'] }),
  policyPublish: def({ method: 'POST', path: '/policies/{policy_id}/publish', source: 'TD-4.4', auth: ['POLICY_ADMIN'] }),

  // Evaluation
  benchmarkRun: def({ method: 'POST', path: '/evaluation/benchmark-runs', source: 'TD-4.4', auth: ['POLICY_ADMIN'] }),

  // Sales Copilot (SCR-S00) — ReAct agent + streaming tiến trình suy luận
  copilotChat: def({ method: 'POST', path: '/copilot/chat', source: 'PROPOSED', auth: 'staff' }),
  copilotChatStream: def({ method: 'POST', path: '/copilot/chat/stream', source: 'PROPOSED', auth: 'staff' }),
} as const

export type EndpointName = keyof typeof ENDPOINTS

/** '/quotes/{quote_id}' + { quote_id: 'Q-1' } → '/quotes/Q-1' */
export function buildPath(path: string, params: Record<string, string | number> = {}): string {
  return path.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = params[key]
    if (value === undefined) throw new Error(`Thiếu tham số đường dẫn "${key}" cho ${path}`)
    return encodeURIComponent(String(value))
  })
}
