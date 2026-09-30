import type { Quote } from './contracts'

/**
 * Backend thật (src/api/endpoints/quotes.py `_format_quote_response`) trả về hồ sơ dạng phẳng
 * (quote_id, unit_code, total_contract_price_vnd, created_by: string, snapshot_payload, …) —
 * KHÔNG có scenarios/recommendation/risk_flag/transaction_context/unit lồng nhau như `Quote`
 * (thiết kế "đề xuất" cũ, chưa khớp backend). Nhiều màn hình (QuoteTable, SaleQuoteDetailPage,
 * QuoteMeta, QuoteResults, ApprovalWorkspacePage…) đọc thẳng các field bắt buộc này mà không
 * kiểm tra null → crash khi chạy với dữ liệu thật.
 *
 * Chuẩn hoá tại tầng API (một chỗ duy nhất) thay vì sửa từng màn hình: điền giá trị mặc định an
 * toàn cho các field còn thiếu, giữ nguyên field đã có (mock-server vẫn trả đủ, không bị ảnh hưởng).
 */
export function normalizeQuote(raw: Record<string, unknown>): Quote {
  const r = raw as Record<string, any>
  const snapshot = (r.snapshot_payload ?? {}) as Record<string, any>
  const unitCode = r.unit_code ?? snapshot.unit_code ?? ''

  const createdBy = r.created_by
  const createdByRef =
    createdBy && typeof createdBy === 'object'
      ? createdBy
      : { user_id: createdBy ?? 'unknown', full_name: createdBy ?? 'Không rõ', role: 'SALE' }

  const unit =
    r.unit && typeof r.unit === 'object'
      ? r.unit
      : {
          unit_code: unitCode,
          project_id: snapshot.project_id ?? '',
          project_name: unitCode || '—',
          block: '',
          floor: 0,
          bedrooms: 0,
          area_m2: 0,
          view: '',
          listed_price_before_tax_vnd: snapshot.listed_price_before_tax_vnd ?? r.total_contract_price_vnd ?? 0,
          status: 'AVAILABLE',
        }

  const transactionContext =
    r.transaction_context && typeof r.transaction_context === 'object'
      ? r.transaction_context
      : {
          unit_code: unitCode,
          transaction_date: null,
          customer_segment: 'NEW_CUSTOMER',
          units_quantity: 1,
          selected_rule_codes: snapshot.selected_rule_codes ?? [],
          objective: snapshot.objective ?? 'MIN_NET_PRICE',
          customer_name: snapshot.customer_name ?? '—',
          customer_phone: snapshot.customer_phone ?? '',
          requested_policy_id: null,
        }

  return {
    quote_id: r.quote_id,
    quote_version: r.quote_version,
    status: r.status,
    pdf_status: r.pdf_status ?? null,
    created_at: r.created_at ?? '',
    updated_at: r.updated_at ?? '',
    created_by: createdByRef,
    submitted_at: r.submitted_at ?? null,
    source_dossier_id: r.source_dossier_id ?? null,
    transaction_context: transactionContext,
    unit,
    policy_snapshot_ref: r.policy_snapshot_ref ?? null,
    conflict_report: r.conflict_report ?? null,
    abstention: r.abstention ?? null,
    missing_fields: r.missing_fields ?? [],
    scenarios: r.scenarios ?? [],
    calculation_validation: r.calculation_validation ?? null,
    recommendation: r.recommendation ?? null,
    risk_flag: r.risk_flag ?? { color: 'GREEN', label: 'Chưa đánh giá', reasons: [] },
    approval: r.approval ?? null,
    artifact_hash: r.artifact_hash ?? r.signature ?? null,
    versions: r.versions ?? [],
  }
}
