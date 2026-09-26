import { useEffect, useState } from 'react'
import { api } from '../client'
import { COMPLIANCE_DEBOUNCE_MS } from '../config'
import type { ComplianceCheckMode, ComplianceCheckResponse, MessageChannel, Quote } from '../contracts'
import { useCommand, queryKeys } from './core'

interface CheckState {
  result: ComplianceCheckResponse | null
  /** Văn bản mà `result` đã kiểm — khác văn bản hiện tại nghĩa là kết quả đã hết hiệu lực. */
  checkedText: string | null
  error: unknown
  errorText: string | null
}

/**
 * Kiểm tra tuân thủ F8 khi soạn: tin mới nạp (Agent soạn) → ON_DRAFT ngay; Sale gõ → DEBOUNCE 500ms.
 * Request cũ bị huỷ khi có văn bản mới để kết quả không bao giờ lệch với nội dung đang hiển thị.
 */
export function useComplianceCheck(text: string, quote: Pick<Quote, 'quote_id' | 'quote_version'>, mode: ComplianceCheckMode) {
  const [state, setState] = useState<CheckState>({ result: null, checkedText: null, error: null, errorText: null })
  const empty = !text.trim()

  useEffect(() => {
    if (empty) return
    const ctrl = new AbortController()
    const timer = setTimeout(
      () => {
        api.compliance
          .check({ message_text: text, mode, quote_id: quote.quote_id, quote_version: quote.quote_version }, ctrl.signal)
          .then((result) => !ctrl.signal.aborted && setState({ result, checkedText: text, error: null, errorText: null }))
          .catch((error) => !ctrl.signal.aborted && setState((s) => ({ ...s, error, errorText: text })))
      },
      mode === 'ON_DRAFT' ? 0 : COMPLIANCE_DEBOUNCE_MS,
    )
    return () => {
      clearTimeout(timer)
      ctrl.abort()
    }
  }, [text, empty, mode, quote.quote_id, quote.quote_version])

  return {
    result: empty ? null : state.result,
    checking: !empty && state.checkedText !== text && state.errorText !== text,
    error: state.errorText === text ? state.error : null,
    stale: !empty && state.checkedText !== null && state.checkedText !== text,
  }
}

export const useDraftMessage = () =>
  useCommand((quote: Pick<Quote, 'quote_id' | 'quote_version'>, key) =>
    api.compliance.draft({ quote_id: quote.quote_id, quote_version: quote.quote_version }, { idempotencyKey: key }),
  )

/** Cổng gửi duy nhất: server chạy lại FINAL_SEND, không tin trạng thái kiểm tra từ trình duyệt. */
export const useSendMessage = () =>
  useCommand(
    (
      vars: { quote: Pick<Quote, 'quote_id' | 'quote_version'>; text: string; check: ComplianceCheckResponse; channel: MessageChannel },
      key,
    ) =>
      api.compliance.send(
        {
          message_text: vars.text,
          message_hash: vars.check.message_hash,
          check_id: vars.check.check_id,
          quote_id: vars.quote.quote_id,
          quote_version: vars.quote.quote_version,
          channel: vars.channel,
        },
        { idempotencyKey: key },
      ),
    { invalidate: (vars) => [queryKeys.audit(vars.quote.quote_id)] },
  )
