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
