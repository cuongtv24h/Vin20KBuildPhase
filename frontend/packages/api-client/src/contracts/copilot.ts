/**
 * Hợp đồng Sales Copilot (SCR-S00) — kênh chat ReAct.
 *
 * Backend: `POST /api/v1/copilot/chat` (gom) và `POST /api/v1/copilot/chat/stream` (SSE).
 * Đây là [ĐỀ XUẤT] mở rộng của hợp đồng cũ (reply/action_type/action_data/suggested_actions) —
 * các trường mới đều optional để UI cũ vẫn chạy nếu backend chưa nâng cấp.
 */

/** Một bước suy luận ReAct để vẽ timeline. */
export type CopilotStepType = 'guardrail' | 'plan' | 'thought' | 'action' | 'observation' | 'final' | 'error'

export interface CopilotCitation {
  policy_id: string
  policy_version?: string | null
  policy_title?: string | null
  rule_code?: string | null
  section?: string | null
  clause_id?: string | null
  quote?: string | null
  document_id?: string | null
  document_hash?: string | null
  effective_from?: string | null
  effective_to?: string | null
  source?: string | null
  score?: number | null
}

export interface CopilotReasoningStep {
  type: CopilotStepType
  /** Văn bản suy nghĩ / tóm tắt quan sát / câu trả lời cuối. */
  text?: string | null
  /** Bước gọi tool: tên tool + tham số. */
  tool?: string | null
  args?: Record<string, unknown> | null
  reason?: string | null
  /** Quan sát: tool chạy thành công hay không. */
  ok?: boolean | null
  summary?: string | null
  citations?: CopilotCitation[]
  iteration?: number | null
  /** Bước của planner (chỉ có ở event `plan`) — câu nhiều ý được chia thành nhiều bước. */
  steps?: { intent: string; tool?: string | null; reason?: string | null }[] | null
}

export interface CopilotChatHistoryItem {
  role: 'user' | 'assistant' | 'agent'
  content: string
}

export interface CopilotChatRequest {
  message: string
  history?: CopilotChatHistoryItem[]
  current_unit?: string | null
  lead_dossier_id?: string | null
  transaction_date?: string | null
  project_id?: string | null
}

/** Payload cuối cùng (frame `final`) — tương thích ngược với ChatResponse cũ. */
export interface CopilotFinalPayload {
  reply: string
  action_type: string | null
  action_data: Record<string, unknown> | null
  suggested_actions: string[]
  citations?: CopilotCitation[]
  grounded?: boolean
  tools_used?: string[]
  iterations?: number
  mode?: 'react' | 'offline_react' | 'guardrail' | 'error'
  /** Critic vòng 2: soi lập luận/phát ngôn ngoài việc đối chiếu số liệu. */
  critique?: { ok: boolean; issues: { code: string; detail: string }[]; hints: string[] } | null
  /** Chi phí ngữ cảnh của lượt: số ký tự Observation, số lần dùng lại cache tool. */
  context_budget?: {
    observation_chars: number
    limit_chars: number
    cached_tool_results: number
    trimmed: boolean
  } | null
}

export interface CopilotChatResponse extends CopilotFinalPayload {
  citations: CopilotCitation[]
  grounded: boolean
  tools_used: string[]
  iterations: number
  mode: 'react' | 'offline_react' | 'guardrail' | 'error'
  reasoning: CopilotReasoningStep[]
}

/** Sự kiện stream: mỗi frame SSE là một bước hoặc payload cuối. */
export type CopilotStreamEvent =
  | ({ type: 'thought' } & CopilotReasoningStep)
  | ({ type: 'action' } & CopilotReasoningStep)
  | ({ type: 'observation' } & CopilotReasoningStep)
  | ({ type: 'guardrail' } & CopilotReasoningStep)
  | ({ type: 'final' } & CopilotFinalPayload)
  | { type: 'error'; message: string }

/** POST /copilot/feedback — phản hồi của Sale về một lượt trả lời (P2). */
export interface CopilotFeedbackRequest {
  message: string
  reply?: string
  /** 1 = hữu ích, -1 = chưa đạt, 0 = trung tính. */
  rating: -1 | 0 | 1
  comment?: string
  tags?: string[]
  mode?: string | null
  tools_used?: string[]
  turn_id?: string | null
}

export interface CopilotFeedbackSummary {
  total: number
  up: number
  down: number
  neutral: number
  satisfaction_rate: number | null
  top_negative_tags: [string, number][]
  /** Phân bố theo chế độ trả lời (react / offline_react / guardrail). */
  by_mode?: { mode: string; count: number }[]
  /** Xu hướng 14 ngày gần nhất, đã điền cả ngày trống. */
  by_day?: { date: string; up: number; down: number }[]
  /** Tool hay xuất hiện ở các lượt bị chê — gợi ý nơi cần cải thiện. */
  top_failing_tools?: [string, number][]
  /** 5 lượt bị chê gần nhất (đã che PII). */
  recent_negative?: CopilotFeedbackEntry[]
}

/** Một dòng trong trang quản trị chất lượng (nội dung đã được server che PII). */
export interface CopilotFeedbackEntry {
  recorded_at: string | null
  rating: number
  label: string
  message: string
  reply: string
  comment: string
  tags: string[]
  mode: string | null
  tools_used: string[]
  turn_id: string | null
}

export interface CopilotFeedbackRecentResponse {
  total: number
  items: CopilotFeedbackEntry[]
}

export interface CopilotFeedbackRecentParams {
  limit?: number
  /** 1 = hữu ích, -1 = chưa đạt, 0 = trung tính. Bỏ trống = tất cả. */
  rating?: -1 | 0 | 1
}

export interface CopilotFeedbackResponse {
  ok: boolean
  recorded_at: string
  summary: CopilotFeedbackSummary
}


// ─── Lịch sử hội thoại Copilot (giữ qua các trang, tra cứu lại được) ─────────

export interface CopilotConversationMessage {
  role: 'user' | 'assistant'
  content: string
  at?: string | null
  citations?: CopilotCitation[]
  action_type?: string | null
}

export interface CopilotConversationSummary {
  conversation_id: string
  title: string
  created_at?: string | null
  updated_at?: string | null
  message_count: number
  last_message: string
}

export interface CopilotConversationDetail extends CopilotConversationSummary {
  messages: CopilotConversationMessage[]
}

export interface CopilotConversationListResponse {
  total: number
  items: CopilotConversationSummary[]
}

export interface CopilotAppendTurnRequest {
  conversation_id?: string | null
  user_message: string
  assistant_message: string
  citations?: CopilotCitation[]
  action_type?: string | null
}
