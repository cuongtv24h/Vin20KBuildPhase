import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../client'
import type { PdfStatus, Quote, QuoteCreatePayload, QuoteCreateRequest, QuoteListParams } from '../contracts'
import { isStaleVersion } from '../errors'
import { queryKeys, useCommand } from './core'

const PDF_IN_FLIGHT: (PdfStatus | null)[] = ['PENDING', 'GENERATING', 'RETRYING']

export const useQuotes = (params: QuoteListParams = {}, options: { live?: boolean } = {}) =>
  useQuery({
    queryKey: queryKeys.quotes({ ...params }),
    queryFn: () => api.quotes.list(params),
    refetchInterval: options.live ? 15_000 : false,
  })

/** `version` bỏ trống = phiên bản mới nhất. Tự làm mới khi PDF đang được worker xử lý. */
export const useQuote = (quoteId: string | undefined, version?: number) =>
  useQuery({
    queryKey: queryKeys.quote(quoteId ?? '', version),
    queryFn: () => api.quotes.get(quoteId ?? '', version),
    enabled: Boolean(quoteId),
    refetchInterval: (q) => (PDF_IN_FLIGHT.includes(q.state.data?.pdf_status ?? null) ? 1_500 : false),
  })

export const useQuoteEvidence = (quote: Pick<Quote, 'quote_id' | 'quote_version'> | undefined, enabled = true) =>
  useQuery({
    queryKey: queryKeys.evidence(quote?.quote_id ?? '', quote?.quote_version ?? 0),
    queryFn: () => api.quotes.evidence(quote?.quote_id ?? '', quote?.quote_version),
    enabled: Boolean(quote) && enabled,
  })

export const useQuoteAudit = (quoteId: string | undefined, refreshKey?: string) =>
  useQuery({
    queryKey: [...queryKeys.audit(quoteId ?? ''), refreshKey ?? ''],
    queryFn: () => api.quotes.audit(quoteId ?? ''),
    enabled: Boolean(quoteId),
  })

export const useQuotePdf = (quoteId: string | undefined, enabled: boolean) =>
  useQuery({
    queryKey: queryKeys.pdf(quoteId ?? ''),
    queryFn: () => api.quotes.pdf(quoteId ?? ''),
    enabled: Boolean(quoteId) && enabled,
    retry: false,
  })

const quoteInvalidations = (quoteId: string) => [queryKeys.quoteRoot(quoteId), ['quotes', 'list'], queryKeys.audit(quoteId), ['leads']]

export const useCreateQuote = () =>
  useCommand((body: QuoteCreatePayload, key) => api.quotes.create(body, { idempotencyKey: key }), {
    invalidate: () => [['quotes', 'list']],
  })

export const useConvertLead = () =>
  useCommand(
    ({ dossierId, body }: { dossierId: string; body: QuoteCreateRequest }, key) =>
      api.leads.convertToQuote(dossierId, body, { idempotencyKey: key }),
    { invalidate: () => [['leads'], ['quotes', 'list']] },
  )

/** Sau khi Quản lý yêu cầu sửa / hệ thống dừng an toàn: tạo phiên bản mới, bản cũ thành SUPERSEDED. */
export const useNewQuoteVersion = () =>
  useCommand(
    ({ quote, body }: { quote: Quote; body: QuoteCreateRequest }, key) =>
      api.quotes.newVersion(quote.quote_id, body, { idempotencyKey: key, expectedVersion: quote.quote_version }),
    { invalidate: ({ quote }) => quoteInvalidations(quote.quote_id) },
  )

function useVersionedCommand<TExtra>(
  run: (quote: Quote, extra: TExtra, key: string) => Promise<Quote>,
) {
  const qc = useQueryClient()
  const command = useCommand(({ quote, extra }: { quote: Quote; extra: TExtra }, key) => run(quote, extra, key), {
    invalidate: ({ quote }) => quoteInvalidations(quote.quote_id),
    onSuccess: (result) => qc.setQueryData(queryKeys.quote(result.quote_id), result),
  })
  return {
    ...command,
    mutateAsync: async (vars: { quote: Quote; extra: TExtra }) => {
      try {
        return await command.mutateAsync(vars)
      } catch (e) {
        // OCC: phiên bản đang xem đã cũ → tải lại để người dùng thấy dữ liệu mới nhất.
        if (isStaleVersion(e)) await Promise.all(quoteInvalidations(vars.quote.quote_id).map((queryKey) => qc.invalidateQueries({ queryKey })))
        throw e
      }
    },
  }
}

export const useSubmitQuote = () =>
  useVersionedCommand<void>((quote, _extra, key) => api.quotes.submit(quote.quote_id, { idempotencyKey: key, expectedVersion: quote.quote_version }))

export const useApproveQuote = () =>
  useVersionedCommand<{ note: string; reauthToken: string }>((quote, extra, key) =>
    api.quotes.approve(quote.quote_id, { note: extra.note }, { idempotencyKey: key, expectedVersion: quote.quote_version, reauthToken: extra.reauthToken }),
  )

export const useRejectQuote = () =>
  useVersionedCommand<{ reason: string }>((quote, extra, key) =>
    api.quotes.reject(quote.quote_id, { reason: extra.reason }, { idempotencyKey: key, expectedVersion: quote.quote_version }),
  )

export const useRequestRevision = () =>
  useVersionedCommand<{ reason: string }>((quote, extra, key) =>
    api.quotes.requestRevision(quote.quote_id, { reason: extra.reason }, { idempotencyKey: key, expectedVersion: quote.quote_version }),
  )

export const useRetryPdf = () =>
  useCommand((quoteId: string, key) => api.quotes.retryPdf(quoteId, { idempotencyKey: key }), {
    invalidate: (quoteId) => quoteInvalidations(quoteId),
  })
