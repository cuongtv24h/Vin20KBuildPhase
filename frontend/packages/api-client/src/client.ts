import type {
  ApproveRequest,
  AuthSession,
  BenchmarkRun,
  ComplianceCheckRequest,
  ComplianceCheckResponse,
  ConfirmConstraintsRequest,
  DecisionReasonRequest,
  DraftMessage,
  DraftMessageRequest,
  ExtractRulesFields,
  HandoffReceipt,
  HandoffRequest,
  LeadDossier,
  LoginRequest,
  MessageSendResult,
  PolicyDocument,
  PreSalesMessageRequest,
  PreSalesSession,
  PreSalesSessionCreate,
  ProjectOverview,
  Quote,
  QuoteAccepted,
  QuoteAudit,
  QuoteCreatePayload,
  QuoteCreateRequest,
  QuoteCreateResult,
  QuoteEvidence,
  QuoteListParams,
  QuotePdf,
  ReauthGrant,
  ReauthRequest,
  RulesTestReport,
  SendMessageCommand,
  UnitSnapshot,
} from './contracts'
import { buildPath, ENDPOINTS, type EndpointName } from './endpoints'
import { http, type HttpRequest } from './http'
import { normalizeQuote } from './normalizeQuote'

/** Tuỳ chọn cho lệnh ghi: khoá idempotency ổn định (hook giữ qua các lần retry) + OCC. */
export interface CommandOptions {
  idempotencyKey?: string
}

export interface VersionedCommandOptions extends CommandOptions {
  /** quote_version đang hiển thị — gửi dưới dạng If-Match. */
  expectedVersion: number
}

type Params = Record<string, string | number>

function call<T>(name: EndpointName, params: Params = {}, init: Omit<HttpRequest, 'method' | 'path'> = {}): Promise<T> {
  const e = ENDPOINTS[name]
  return http<T>({ method: e.method, path: buildPath(e.path, params), ...init })
}

export const api = {
  auth: {
    login: (body: LoginRequest, o: CommandOptions = {}) => call<AuthSession>('authLogin', {}, { json: body, ...o }),
    logout: () => call<void>('authLogout'),
    reauth: (body: ReauthRequest, o: CommandOptions = {}) => call<ReauthGrant>('authReauth', {}, { json: body, ...o }),
  },

  catalog: {
    projects: () => call<ProjectOverview[]>('publicProjects'),
    units: (query: { project_id?: string } = {}) => call<UnitSnapshot[]>('units', {}, { query }),
    policies: (query: { project_id?: string; status?: string } = {}) => call<PolicyDocument[]>('policyList', {}, { query }),
    activePolicy: (query: { project_id: string; date: string }) => call<PolicyDocument | null>('policyActive', {}, { query }),
    policy: (policyId: string) => call<PolicyDocument>('policyDetail', { policy_id: policyId }),
  },

  quotes: {
    /**
     * Backend thật trả `{ total, limit, offset, items }` (không phải mảng trần) và mỗi item ở
     * dạng phẳng — chuẩn hoá qua `normalizeQuote` để khớp shape `Quote[]` các màn hình đang dùng.
     */
    list: async (params: QuoteListParams = {}) => {
      const res = await call<Quote[] | { items: Record<string, unknown>[] }>(
        'quoteList',
        {},
        { query: { status: params.status?.join(','), source_dossier_id: params.source_dossier_id } },
      )
      const items = Array.isArray(res) ? res : res.items
      return items.map((q) => normalizeQuote(q as unknown as Record<string, unknown>))
    },
    get: async (quoteId: string, version?: number) => {
      const res = await call<Record<string, unknown>>('quoteDetail', { quote_id: quoteId }, { query: { version } })
      return normalizeQuote(res)
    },
    /** POST /api/v1/quotes thật — đồng bộ, trả về hồ sơ đầy đủ ngay (không phải 202 + SSE). */
    create: (body: QuoteCreatePayload, o: CommandOptions = {}) => call<QuoteCreateResult>('quoteCreate', {}, { json: body, ...o }),
    newVersion: (quoteId: string, body: QuoteCreateRequest, o: VersionedCommandOptions) =>
      call<QuoteAccepted>('quoteNewVersion', { quote_id: quoteId }, { json: body, idempotencyKey: o.idempotencyKey, ifMatchVersion: o.expectedVersion }),
    submit: (quoteId: string, o: VersionedCommandOptions) =>
      call<Quote>('quoteSubmit', { quote_id: quoteId }, { idempotencyKey: o.idempotencyKey, ifMatchVersion: o.expectedVersion }),
    approve: (quoteId: string, body: ApproveRequest, o: VersionedCommandOptions & { reauthToken: string }) =>
      call<Quote>('quoteApprove', { quote_id: quoteId }, {
        json: body,
        idempotencyKey: o.idempotencyKey,
        ifMatchVersion: o.expectedVersion,
        headers: { 'X-Reauth-Token': o.reauthToken },
      }),
    reject: (quoteId: string, body: DecisionReasonRequest, o: VersionedCommandOptions) =>
      call<Quote>('quoteReject', { quote_id: quoteId }, { json: body, idempotencyKey: o.idempotencyKey, ifMatchVersion: o.expectedVersion }),
    requestRevision: (quoteId: string, body: DecisionReasonRequest, o: VersionedCommandOptions) =>
      call<Quote>('quoteRevision', { quote_id: quoteId }, { json: body, idempotencyKey: o.idempotencyKey, ifMatchVersion: o.expectedVersion }),
    evidence: (quoteId: string, version?: number) => call<QuoteEvidence>('quoteEvidence', { quote_id: quoteId }, { query: { version } }),
    audit: (quoteId: string) => call<QuoteAudit>('quoteAudit', { quote_id: quoteId }),
    pdf: (quoteId: string) => call<QuotePdf>('quotePdf', { quote_id: quoteId }),
    retryPdf: (quoteId: string, o: CommandOptions = {}) => call<Quote>('quotePdfRetry', { quote_id: quoteId }, o),
    /** Đường dẫn SSE dự phòng khi không còn `stream_url` từ 202 (vd. tải lại trang). */
    eventsPath: (quoteId: string) => buildPath(ENDPOINTS.quoteEvents.path, { quote_id: quoteId }),
  },

  leads: {
    list: () => call<LeadDossier[]>('leadList'),
    convertToQuote: (dossierId: string, body: QuoteCreateRequest, o: CommandOptions = {}) =>
      call<QuoteAccepted>('leadConvert', { dossier_id: dossierId }, { json: body, ...o }),
  },

  preSales: {
    create: (body: PreSalesSessionCreate, o: CommandOptions = {}) => call<PreSalesSession>('preSalesCreate', {}, { json: body, ...o }),
    get: (sessionId: string) => call<PreSalesSession>('preSalesGet', { session_id: sessionId }),
    sendMessage: (sessionId: string, body: PreSalesMessageRequest, o: CommandOptions = {}) =>
      call<PreSalesSession>('preSalesMessage', { session_id: sessionId }, { json: body, ...o }),
    confirmConstraints: (sessionId: string, body: ConfirmConstraintsRequest, o: CommandOptions = {}) =>
      call<PreSalesSession>('preSalesConfirm', { session_id: sessionId }, { json: body, ...o }),
    generatePlan: (sessionId: string, o: CommandOptions = {}) => call<PreSalesSession>('preSalesPlan', { session_id: sessionId }, o),
    handoff: (sessionId: string, body: HandoffRequest, o: CommandOptions = {}) =>
      call<HandoffReceipt>('preSalesHandoff', { session_id: sessionId }, { json: body, ...o }),
  },

  compliance: {
    check: (body: ComplianceCheckRequest, signal?: AbortSignal) =>
      call<ComplianceCheckResponse>('complianceCheck', {}, { json: body, signal }),
    draft: (body: DraftMessageRequest, o: CommandOptions = {}) => call<DraftMessage>('complianceDraft', {}, { json: body, ...o }),
    send: (body: SendMessageCommand, o: CommandOptions = {}) => call<MessageSendResult>('messageSend', {}, { json: body, ...o }),
  },

  policies: {
    extractRules: (fields: ExtractRulesFields, file: File, o: CommandOptions = {}) => {
      const form = new FormData()
      for (const [k, v] of Object.entries(fields)) form.append(k, v)
      form.append('file', file)
      return call<PolicyDocument>('policyExtract', {}, { form, ...o })
    },
    testRules: (policyId: string, o: CommandOptions = {}) => call<RulesTestReport>('policyRulesTest', { policy_id: policyId }, o),
    publish: (policyId: string, o: CommandOptions = {}) => call<PolicyDocument>('policyPublish', { policy_id: policyId }, o),
  },

  evaluation: {
    runBenchmark: (o: CommandOptions = {}) => call<BenchmarkRun>('benchmarkRun', {}, o),
  },
}
