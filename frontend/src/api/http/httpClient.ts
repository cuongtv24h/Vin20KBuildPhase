import type {
  AnalysisOptions,
  AnalysisProgressEvent,
  ApiClient,
  CreateQuoteRequest,
} from '@/api/contracts'
import { ApiError } from '@/api/errors'
import type { Quote } from '@/types/domain'

/**
 * ApiClient gọi REST backend thật. Quy ước:
 * - Base URL: VITE_API_BASE_URL (mặc định `/api/v1`).
 * - Xác thực: `Authorization: Bearer <accessToken>`.
 * - Lỗi: HTTP status ≠ 2xx với body `{ code, message }` → ApiError.
 * - Phân tích báo giá: POST trả 202 `{ quoteId }`, tiến trình qua SSE
 *   `GET /quotes/{id}/events?access_token=` (event `progress` → AnalysisProgressEvent,
 *   event `completed` → kết thúc), sau đó GET /quotes/{id}.
 */
export function createHttpClient(baseUrl: string, getAccessToken: () => string | null): ApiClient {
  const base = baseUrl.replace(/\/$/, '')

  async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const token = getAccessToken()
    const res = await fetch(`${base}${path}`, {
      method,
      headers: {
        Accept: 'application/json',
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    if (!res.ok) {
      let code = 'HTTP_ERROR'
      let message = `Yêu cầu thất bại (${res.status}).`
      try {
        const payload = (await res.json()) as { code?: string; message?: string; detail?: string }
        code = payload.code ?? code
        message = payload.message ?? payload.detail ?? message
      } catch {
        // body không phải JSON
      }
      throw new ApiError(res.status, code, message)
    }
    if (res.status === 204) return undefined as T
    return (await res.json()) as T
  }

  const qs = (params: Record<string, string | number | undefined>) => {
    const search = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== '') search.set(k, String(v))
    const s = search.toString()
    return s ? `?${s}` : ''
  }

  function streamProgress(quoteId: string, options?: AnalysisOptions): Promise<void> {
    if (!options?.onProgress || typeof EventSource === 'undefined') return Promise.resolve()
    const token = getAccessToken() ?? ''
    return new Promise((resolve) => {
      const source = new EventSource(`${base}/quotes/${encodeURIComponent(quoteId)}/events${qs({ access_token: token })}`)
      source.addEventListener('progress', (e) => {
        options.onProgress?.(JSON.parse((e as MessageEvent<string>).data) as AnalysisProgressEvent)
      })
      const done = () => {
        source.close()
        resolve()
      }
      source.addEventListener('completed', done)
      source.onerror = done
    })
  }

  async function analyze(path: string, input: CreateQuoteRequest, options?: AnalysisOptions): Promise<Quote> {
    const { quoteId } = await request<{ quoteId: string }>('POST', path, input)
    await streamProgress(quoteId, options)
    return request<Quote>('GET', `/quotes/${encodeURIComponent(quoteId)}`)
  }

  const enc = encodeURIComponent

  return {
    auth: {
      login: (input) => request('POST', '/auth/login', input),
      logout: () => request('POST', '/auth/logout'),
    },
    catalog: {
      listProjects: () => request('GET', '/projects'),
      listUnits: (filter) => request('GET', `/units${qs({ ...filter })}`),
      getUnit: (unitCode) => request('GET', `/units/${enc(unitCode)}`),
      listPaymentPlans: () => request('GET', '/payment-plans'),
      getActivePolicy: (projectId, date) => request('GET', `/policies/active${qs({ projectId, date })}`),
    },
    public: {
      listProjectOverviews: () => request('GET', '/public/projects'),
      estimate: (input) => request('POST', '/public/estimates', input),
      submitLead: (input) => request('POST', '/public/leads', input),
      getSharedQuote: (token) => request('GET', `/public/quotes/${enc(token)}`),
      respondToQuote: (token, input) => request('POST', `/public/quotes/${enc(token)}/response`, input),
      verifySharedQuote: (token) => request('GET', `/public/quotes/${enc(token)}/verify`),
    },
    leads: {
      list: (params) => request('GET', `/leads${qs({ scope: params.scope })}`),
      get: (leadId) => request('GET', `/leads/${enc(leadId)}`),
      claim: (leadId) => request('POST', `/leads/${enc(leadId)}/claim`),
      updateStatus: (leadId, input) => request('PATCH', `/leads/${enc(leadId)}`, input),
    },
    quotes: {
      list: (params) => request('GET', `/quotes${qs({ status: params?.status?.join(','), leadId: params?.leadId })}`),
      get: (quoteId) => request('GET', `/quotes/${enc(quoteId)}`),
      preflight: (input) => request('POST', '/quotes/preflight', input),
      create: (input, options) => analyze('/quotes', input, options),
      revise: (quoteId, input, options) => analyze(`/quotes/${enc(quoteId)}/revisions`, input, options),
      submit: (quoteId) => request('POST', `/quotes/${enc(quoteId)}/submit`),
      decide: (quoteId, input) => request('POST', `/quotes/${enc(quoteId)}/decision`, input),
      share: (quoteId, input) => request('POST', `/quotes/${enc(quoteId)}/share`, input),
      verify: (quoteId) => request('GET', `/quotes/${enc(quoteId)}/verify`),
    },
    policies: {
      list: () => request('GET', '/policies'),
      get: (policyId) => request('GET', `/policies/${enc(policyId)}`),
      createDraft: (input) => request('POST', '/policies', input),
      updateDraft: (policyId, input) => request('PATCH', `/policies/${enc(policyId)}`, input),
      runPublishChecks: (policyId) => request('POST', `/policies/${enc(policyId)}/checks`),
      publish: (policyId) => request('POST', `/policies/${enc(policyId)}/publish`),
      archive: (policyId) => request('POST', `/policies/${enc(policyId)}/archive`),
    },
    inventory: {
      updateUnit: (unitCode, input) => request('PATCH', `/units/${enc(unitCode)}`, input),
    },
    qa: {
      runFormulaRegression: () => request('POST', '/qa/formula-regression'),
    },
  }
}
