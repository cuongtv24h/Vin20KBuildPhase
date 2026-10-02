import type { CopilotAppendTurnRequest, CopilotFinalPayload } from './contracts'

/**
 * Dựng payload lưu một lượt hỏi–đáp Copilot vào lịch sử.
 *
 * Quy tắc quan trọng: **lưu MỌI lượt**, kể cả câu trả lời chưa đối chiếu được dữ liệu
 * (`mode = offline_react`, `citations` rỗng — đúng thứ xảy ra khi backend chưa cấu hình khoá LLM).
 *
 * Vì sao tách ra đây: bản trước nằm inline trong `SalesWorkspacePage` và **bỏ qua** những lượt như
 * vậy ("mở lại sẽ không còn cảnh báo"). Hậu quả thật: trên môi trường chạy chế độ dự phòng, không
 * lượt nào được lưu → khung "Lịch sử hội thoại" luôn rỗng và đổi trang là mất cả cuộc đang dở.
 * Dấu hiệu "chưa đối chiếu" không mất, vì khi mở lại UI suy ra từ `citations` rỗng.
 */
export function turnToAppendPayload(input: {
  conversationId: string | null
  question: string
  final: Pick<CopilotFinalPayload, 'reply' | 'citations' | 'action_type'>
}): CopilotAppendTurnRequest {
  return {
    conversation_id: input.conversationId,
    user_message: input.question,
    assistant_message: input.final.reply,
    citations: input.final.citations ?? [],
    action_type: input.final.action_type ?? null,
  }
}
