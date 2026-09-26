import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type {
  AnalysisProgressEvent,
  ApprovalDecisionRequest,
  CreateLeadRequest,
  CreateQuoteRequest,
  CustomerResponseRequest,
  EstimateRequest,
  LeadListParams,
  LoginRequest,
  PreflightRequest,
  QuoteListParams,
  ShareQuoteRequest,
  UnitFilter,
  UpdatePolicyDraftRequest,
  UpdateUnitRequest,
} from '@/api/contracts'
import { api } from '@/api'

/** Query key tập trung — dùng để invalidate đúng phạm vi sau mỗi mutation. */
export const queryKeys = {
  projects: ['projects'] as const,
  projectOverviews: ['public', 'projects'] as const,
  units: (filter: UnitFilter = {}) => ['units', 'list', filter] as const,
  unit: (unitCode: string) => ['units', 'detail', unitCode] as const,
  paymentPlans: ['payment-plans'] as const,
  activePolicy: (projectId: string, date: string) => ['policies', 'active', projectId, date] as const,
  estimate: (input: EstimateRequest) => ['public', 'estimate', input] as const,
  sharedQuote: (token: string) => ['public', 'quote', token] as const,
  leads: (params: LeadListParams) => ['leads', 'list', params] as const,
  lead: (leadId: string) => ['leads', 'detail', leadId] as const,
  quotes: (params: QuoteListParams = {}) => ['quotes', 'list', params] as const,
  quote: (quoteId: string) => ['quotes', 'detail', quoteId] as const,
  preflight: (input: PreflightRequest) => ['quotes', 'preflight', input] as const,
  policies: ['policies', 'list'] as const,
  policy: (policyId: string) => ['policies', 'detail', policyId] as const,
}

// ─── Queries ───────────────────────────────────────────────────────────────

export const useProjects = () => useQuery({ queryKey: queryKeys.projects, queryFn: () => api.catalog.listProjects() })

export const useProjectOverviews = () =>
  useQuery({ queryKey: queryKeys.projectOverviews, queryFn: () => api.public.listProjectOverviews() })

export const useUnits = (filter: UnitFilter = {}) =>
  useQuery({ queryKey: queryKeys.units(filter), queryFn: () => api.catalog.listUnits(filter) })

export const useUnit = (unitCode: string | undefined) =>
  useQuery({
    queryKey: queryKeys.unit(unitCode ?? ''),
    queryFn: () => api.catalog.getUnit(unitCode ?? ''),
    enabled: Boolean(unitCode),
  })

export const usePaymentPlans = () =>
  useQuery({ queryKey: queryKeys.paymentPlans, queryFn: () => api.catalog.listPaymentPlans(), staleTime: Infinity })

export const useActivePolicy = (projectId: string | undefined, date: string) =>
  useQuery({
    queryKey: queryKeys.activePolicy(projectId ?? '', date),
    queryFn: () => api.catalog.getActivePolicy(projectId ?? '', date),
    enabled: Boolean(projectId && date),
  })

export const useEstimate = (input: EstimateRequest | null) =>
  useQuery({
    queryKey: queryKeys.estimate(input ?? { unitCode: '', customerSegment: 'NEW_CUSTOMER' }),
    queryFn: () => api.public.estimate(input!),
    enabled: Boolean(input?.unitCode),
    placeholderData: keepPreviousData,
  })

export const useSharedQuote = (token: string | undefined) =>
  useQuery({
    queryKey: queryKeys.sharedQuote(token ?? ''),
    queryFn: () => api.public.getSharedQuote(token ?? ''),
    enabled: Boolean(token),
    retry: false,
  })

export const useLeads = (params: LeadListParams) =>
  useQuery({ queryKey: queryKeys.leads(params), queryFn: () => api.leads.list(params) })

export const useLead = (leadId: string | null | undefined) =>
  useQuery({
    queryKey: queryKeys.lead(leadId ?? ''),
    queryFn: () => api.leads.get(leadId ?? ''),
    enabled: Boolean(leadId),
  })

export const useQuotes = (params: QuoteListParams = {}) =>
  useQuery({ queryKey: queryKeys.quotes(params), queryFn: () => api.quotes.list(params) })

export const useQuote = (quoteId: string | undefined) =>
  useQuery({
    queryKey: queryKeys.quote(quoteId ?? ''),
    queryFn: () => api.quotes.get(quoteId ?? ''),
    enabled: Boolean(quoteId),
  })

export const usePreflight = (input: PreflightRequest | null) =>
  useQuery({
    queryKey: queryKeys.preflight(
      input ?? { unitCode: '', transactionDate: '', customerSegment: 'NEW_CUSTOMER', unitsQuantity: 1, selectedRuleCodes: [] },
    ),
    queryFn: () => api.quotes.preflight(input!),
    enabled: Boolean(input?.unitCode && input.transactionDate),
    placeholderData: keepPreviousData,
  })

export const usePolicies = () => useQuery({ queryKey: queryKeys.policies, queryFn: () => api.policies.list() })

export const usePolicy = (policyId: string | undefined) =>
  useQuery({
    queryKey: queryKeys.policy(policyId ?? ''),
    queryFn: () => api.policies.get(policyId ?? ''),
    enabled: Boolean(policyId),
  })

// ─── Mutations ─────────────────────────────────────────────────────────────

export const useLogin = () => useMutation({ mutationFn: (input: LoginRequest) => api.auth.login(input) })

export const useSubmitLead = () => useMutation({ mutationFn: (input: CreateLeadRequest) => api.public.submitLead(input) })

export function useRespondToQuote(token: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: CustomerResponseRequest) => api.public.respondToQuote(token, input),
    onSuccess: (view) => qc.setQueryData(queryKeys.sharedQuote(token), view),
  })
}

export const useVerifySharedQuote = (token: string) =>
  useMutation({ mutationFn: () => api.public.verifySharedQuote(token) })

function useInvalidate() {
  const qc = useQueryClient()
  return (...roots: string[]) => Promise.all(roots.map((root) => qc.invalidateQueries({ queryKey: [root] })))
}

export function useClaimLead() {
  const invalidate = useInvalidate()
  return useMutation({ mutationFn: (leadId: string) => api.leads.claim(leadId), onSuccess: () => invalidate('leads') })
}

export interface AnalyzeVariables {
  input: CreateQuoteRequest
  quoteId?: string
  onProgress?: (e: AnalysisProgressEvent) => void
}

/** Tạo mới (không có quoteId) hoặc phân tích lại phiên bản mới (có quoteId). */
export function useAnalyzeQuote() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ input, quoteId, onProgress }: AnalyzeVariables) =>
      quoteId ? api.quotes.revise(quoteId, input, { onProgress }) : api.quotes.create(input, { onProgress }),
    onSuccess: () => invalidate('quotes', 'leads'),
  })
}

export function useSubmitQuote() {
  const invalidate = useInvalidate()
  return useMutation({ mutationFn: (quoteId: string) => api.quotes.submit(quoteId), onSuccess: () => invalidate('quotes') })
}

export function useDecideQuote() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ quoteId, ...input }: ApprovalDecisionRequest & { quoteId: string }) => api.quotes.decide(quoteId, input),
    onSuccess: () => invalidate('quotes'),
  })
}

export function useShareQuote() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ quoteId, ...input }: ShareQuoteRequest & { quoteId: string }) => api.quotes.share(quoteId, input),
    onSuccess: () => invalidate('quotes', 'leads'),
  })
}

export const useVerifyQuote = () => useMutation({ mutationFn: (quoteId: string) => api.quotes.verify(quoteId) })

export function useCreatePolicyDraft() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (fromPolicyId: string) => api.policies.createDraft({ fromPolicyId }),
    onSuccess: () => invalidate('policies'),
  })
}

export function useUpdatePolicyDraft() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ policyId, ...patch }: UpdatePolicyDraftRequest & { policyId: string }) => api.policies.updateDraft(policyId, patch),
    onSuccess: () => invalidate('policies'),
  })
}

export const useRunPublishChecks = () =>
  useMutation({ mutationFn: (policyId: string) => api.policies.runPublishChecks(policyId) })

export function usePublishPolicy() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (policyId: string) => api.policies.publish(policyId),
    onSuccess: () => invalidate('policies', 'public'),
  })
}

export function useArchivePolicy() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (policyId: string) => api.policies.archive(policyId),
    onSuccess: () => invalidate('policies', 'public'),
  })
}

export function useUpdateUnit() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ unitCode, ...input }: UpdateUnitRequest & { unitCode: string }) => api.inventory.updateUnit(unitCode, input),
    onSuccess: () => invalidate('units', 'public'),
  })
}

export const useRunFormulaRegression = () => useMutation({ mutationFn: () => api.qa.runFormulaRegression() })
