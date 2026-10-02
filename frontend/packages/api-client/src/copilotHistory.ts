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
  final: Pick<
    CopilotFinalPayload,
    'reply' | 'citations' | 'action_type' | 'internal_notes' | 'anchors' | 'data_as_of'
  >
}): CopilotAppendTurnRequest {
  return {
    conversation_id: input.conversationId,
    user_message: input.question,
    assistant_message: input.final.reply,
    citations: input.final.citations ?? [],
    action_type: input.final.action_type ?? null,
    // Cả ba trường dưới đây phải sống cùng hội thoại: mở lại lịch sử vẫn thấy mỏ neo bấm được,
    // cảnh báo kiểm duyệt và mốc thời gian dữ liệu (chốt P2.1/P2.4/P1.6).
    internal_notes: input.final.internal_notes ?? '',
    anchors: input.final.anchors ?? [],
    data_as_of: input.final.data_as_of ?? null,
  }
}

//: Nhãn nguồn gốc của số do Sale tự nhập — do backend sinh (`anchors.py`), copy cho khách phải bỏ đi.
const INPUT_LABEL_RE = /\s*\((?:ngân sách|số) anh\/chị nhập\)/g
//: Mỏ neo `[n]` là dấu đối chiếu nội bộ — khách không cần thấy.
const ANCHOR_RE = /\[\d{1,2}\]/g

/**
 * Biến câu trả lời của Copilot thành văn bản **gửi thẳng cho khách**.
 *
 * Bỏ ba thứ chỉ có nghĩa trong nội bộ: mỏ neo `[n]`, nhãn "(ngân sách anh/chị nhập)" và ký hiệu
 * markdown (**đậm**, *nghiêng*) — Zalo/SMS không render markdown nên để lại chỉ rối tin nhắn.
 */
export function customerReadyText(reply: string): string {
  return (reply || '')
    .replace(ANCHOR_RE, '')
    .replace(INPUT_LABEL_RE, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/(^|\s)\*([^*\n]+)\*(?=\s|$)/g, '$1$2')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
