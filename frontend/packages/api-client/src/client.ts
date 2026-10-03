import type {
  CopilotFeedbackRecentParams,
  CopilotFeedbackRecentResponse,
  CopilotFeedbackRequest,
  CopilotFeedbackResponse,
  CopilotFeedbackSummary,
  AdminSetupStatus,
  CopilotChatRequest,
  CopilotChatResponse,
  AdminUser,
  ApproveRequest,
  AuthSession,
  BenchmarkRun,
  ComplianceCheckRequest,
  ComplianceCheckResponse,
  ConfirmConstraintsRequest,
  CreateUserPayload,
  DecisionReasonRequest,
  DraftMessage,
  DraftMessageRequest,
  ExtractRulesFields,
  HandoffReceipt,
  HandoffRequest,
  InitAdminPayload,
  LeadCreatePayload,
  LeadUpdatePayload,
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
  QuoteCreateOutcome,
  QuoteCreatePayload,
  QuoteCreateRequest,
  QuoteEvidence,
  QuoteListParams,
  QuotePdf,
  ReauthGrant,
  CopilotAppendTurnRequest,
  CopilotConversationDetail,
  CopilotConversationListResponse,
  LlmProvider,
  LlmProviderListResponse,
  LlmProviderPayload,
  LlmProviderTestResult,
  LlmUsageRecordsResponse,
  LlmUsageSummary,
  ReauthRequest,
  RulesTestReport,
  SendMessageCommand,
  TtsFeedbackPayload,
  TtsFeedbackResponse,
  TtsProviderAdmin,
  TtsProviderListResponse,
  TtsProviderPayload,
  TtsProviderTestResult,
  TtsSettingsPayload,
  TtsSettingsResponse,
  UnitSnapshot,
  UpdateUserPayload,
} from './contracts'
import { streamCopilotChat } from './copilotStream'
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

  admin: {
    setupStatus: () => call<AdminSetupStatus>('adminSetupStatus'),
    setup: (body: InitAdminPayload) =>
      call<{ status: string; message: string; access_token: string; expires_at: string; user: AdminUser }>('adminSetup', {}, { json: body }),
    users: (query: { role?: string; search?: string } = {}) => call<AdminUser[]>('adminUsersList', {}, { query }),
    createUser: (body: CreateUserPayload) => call<AdminUser>('adminUserCreate', {}, { json: body }),
    updateUser: (userId: string, body: UpdateUserPayload) => call<AdminUser>('adminUserUpdate', { user_id: userId }, { json: body }),
    deleteUser: (userId: string) => call<{ status: string; message: string }>('adminUserDelete', { user_id: userId }),
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
    /**
     * POST /api/v1/quotes. Body nhận cả `QuoteCreatePayload` (backend thật, đồng bộ)
     * lẫn `TransactionContext` (TD-4.1/mock: 202 + SSE) — xem `QuoteCreateOutcome`.
     */
    create: (body: QuoteCreatePayload | QuoteCreateRequest, o: CommandOptions = {}) =>
      call<QuoteCreateOutcome>('quoteCreate', {}, { json: body, ...o }),
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
    list: async () => {
      const res = await call<any>('leadList')
      if (Array.isArray(res)) return res as LeadDossier[]
      if (res && Array.isArray(res.items)) return res.items as LeadDossier[]
      return []
    },
    get: (dossierId: string) => call<LeadDossier>('leadGet', { dossier_id: dossierId }),
    create: (body: LeadCreatePayload, o: CommandOptions = {}) => call<LeadDossier>('leadCreate', {}, { json: body, ...o }),
    update: (dossierId: string, body: LeadUpdatePayload, o: CommandOptions = {}) =>
      call<LeadDossier>('leadUpdate', { dossier_id: dossierId }, { json: body, ...o }),
    delete: (dossierId: string, o: CommandOptions = {}) => call<{ deleted: boolean }>('leadDelete', { dossier_id: dossierId }, o),
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
    /** `body` tuỳ chọn: gắn lần chạy với văn bản chính sách đang chuẩn bị ban hành (bằng chứng release gate). */
    runBenchmark: (body: { policy_id?: string; policy_version?: string } = {}, o: CommandOptions = {}) =>
      call<BenchmarkRun>('benchmarkRun', {}, { json: body, ...o }),
  },

  copilot: {
    /** Chat gom (không stream) — dùng khi môi trường chặn SSE. */
    chat: (body: CopilotChatRequest, signal?: AbortSignal) =>
      call<CopilotChatResponse>('copilotChat', {}, { json: body, signal }),
    /**
     * Chat stream tiến trình ReAct. Trả về hàm huỷ.
     * Caller tự quản lý state qua handlers.onEvent.
     */
    stream: (body: CopilotChatRequest, handlers: Parameters<typeof streamCopilotChat>[1], signal?: AbortSignal) =>
      streamCopilotChat(body, handlers, signal),
    /** Gửi đánh giá của Sale về một lượt trả lời (P2 — học từ phản hồi). */
    feedback: (body: CopilotFeedbackRequest, o: CommandOptions = {}) =>
      call<CopilotFeedbackResponse>('copilotFeedback', {}, { json: body, ...o }),
    /** Thống kê phản hồi tích luỹ (dashboard chất lượng). */
    feedbackSummary: (signal?: AbortSignal) => call<CopilotFeedbackSummary>('copilotFeedbackSummary', {}, { signal }),
    /**
     * Danh sách phản hồi chi tiết cho trang quản trị chất lượng (ADMIN/POLICY_ADMIN).
     * Nội dung đã được server che PII trước khi trả về.
     */
    feedbackRecent: (params: CopilotFeedbackRecentParams = {}, signal?: AbortSignal) =>
      call<CopilotFeedbackRecentResponse>('copilotFeedbackRecent', {}, { query: { ...params }, signal }),

    // ─── Lịch sử hội thoại (giữ qua các trang, tra cứu lại được) ─────────────
    conversations: (signal?: AbortSignal) =>
      call<CopilotConversationListResponse>('copilotConversations', {}, { signal }),
    conversationCreate: (body: { title?: string } = {}, o: CommandOptions = {}) =>
      call<CopilotConversationDetail>('copilotConversationCreate', {}, { json: body, ...o }),
    conversation: (conversationId: string, signal?: AbortSignal) =>
      call<CopilotConversationDetail>('copilotConversationDetail', { conversation_id: conversationId }, { signal }),
    /** Ghi một lượt hỏi–đáp; bỏ trống `conversation_id` để tạo cuộc mới. */
    appendTurn: (body: CopilotAppendTurnRequest, o: CommandOptions = {}) =>
      call<CopilotConversationDetail>('copilotConversationTurn', {}, { json: body, ...o }),
    conversationRename: (conversationId: string, title: string, o: CommandOptions = {}) =>
      call<CopilotConversationDetail>('copilotConversationRename', { conversation_id: conversationId }, { json: { title }, ...o }),
    conversationDelete: (conversationId: string, o: CommandOptions = {}) =>
      call<{ ok: boolean; conversation_id: string }>('copilotConversationDelete', { conversation_id: conversationId }, o),
  },

  llmAdmin: {
    /** Danh sách nhà cung cấp Admin khai báo (DB trước, ENV sau). */
    providers: (signal?: AbortSignal) => call<LlmProviderListResponse>('llmProviders', {}, { signal }),
    createProvider: (body: LlmProviderPayload, o: CommandOptions = {}) =>
      call<LlmProvider>('llmProviderCreate', {}, { json: body, ...o }),
    updateProvider: (providerId: string, body: LlmProviderPayload, o: CommandOptions = {}) =>
      call<LlmProvider>('llmProviderUpdate', { provider_id: providerId }, { json: body, ...o }),
    deleteProvider: (providerId: string, o: CommandOptions = {}) =>
      call<{ ok: boolean; provider_id: string }>('llmProviderDelete', { provider_id: providerId }, o),
    testProvider: (providerId: string, o: CommandOptions = {}) =>
      call<LlmProviderTestResult>('llmProviderTest', { provider_id: providerId }, { json: {}, ...o }),
    /** Tab "Chi phí & hiệu năng": token, chi phí theo đơn giá, p50/p95, tỉ lệ lỗi. */
    usageSummary: (days = 14, signal?: AbortSignal) =>
      call<LlmUsageSummary>('llmUsageSummary', {}, { query: { days }, signal }),
    usageRecords: (limit = 50, signal?: AbortSignal) =>
      call<LlmUsageRecordsResponse>('llmUsageRecords', {}, { query: { limit }, signal }),
  },

  /** Đọc câu trả lời Copilot (TTS): thiết lập giọng đọc + phản hồi chất lượng giọng. */
  tts: {
    settings: (signal?: AbortSignal) => call<TtsSettingsResponse>('ttsSettings', {}, { signal }),
    updateSettings: (body: TtsSettingsPayload, o: CommandOptions = {}) =>
      call<TtsSettingsResponse>('ttsSettingsUpdate', {}, { json: body, ...o }),
    /** Ai cũng gửi được (kèm danh tính trong token) — dữ liệu để chọn giọng theo thực tế. */
    feedback: (body: TtsFeedbackPayload, o: CommandOptions = {}) =>
      call<TtsFeedbackResponse>('ttsFeedback', {}, { json: body, ...o }),
  },

  /** Quản trị nhà cung cấp TTS (ADMIN) — nhập khoá, test kết nối, thêm nhà cung cấp mới. */
  ttsAdmin: {
    providers: (signal?: AbortSignal) => call<TtsProviderListResponse>('ttsProviders', {}, { signal }),
    createProvider: (body: TtsProviderPayload, o: CommandOptions = {}) =>
      call<TtsProviderAdmin>('ttsProviderCreate', {}, { json: body, ...o }),
    updateProvider: (providerId: string, body: TtsProviderPayload, o: CommandOptions = {}) =>
      call<TtsProviderAdmin>('ttsProviderUpdate', { provider_id: providerId }, { json: body, ...o }),
    deleteProvider: (providerId: string, o: CommandOptions = {}) =>
      call<{
        ok: boolean
        provider_id: string
        provider: string
        still_available: boolean
        /** Số phạm vi thiết lập (mặc định/hồ sơ riêng) đang chọn nhà cung cấp này. */
        used_by_scopes: number
      }>('ttsProviderDelete', { provider_id: providerId }, o),
    /** Nhận cả `provider_id` lẫn mã nhà cung cấp dựng sẵn (ví dụ `openai`). */
    testProvider: (providerRef: string, o: CommandOptions = {}) =>
      call<TtsProviderTestResult>('ttsProviderTest', { provider_id: providerRef }, { json: {}, ...o }),
  },
}
