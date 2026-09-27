import { create } from 'zustand'
import { getDemoScenario } from '@/data/demoScenarios'
import { QUOTES_SEED } from '@/data/quotes.store'
import { getUnitByCode } from '@/data/units.mock'
import {
  buildApprovalRecord,
  buildForcedCalculationFailureQuote,
  buildQuoteFromContext,
  buildSnapshot,
  hashSnapshot,
  resetQuoteSequence,
} from '@/engine/quoteFactory'
import type { Quote, TransactionContext, UserRole } from '@/types/domain'

export interface ActionNotification {
  id: number
  text: string
}

interface AppState {
  role: UserRole
  quotes: Quote[]
  lastActionMessage: ActionNotification | null

  setRole: (role: UserRole) => void
  submitFromCopilot: (context: TransactionContext) => Quote
  sendForReview: (quoteId: string) => void
  approveQuote: (quoteId: string, approverName: string, notes: string) => Promise<void>
  rejectQuote: (quoteId: string, approverName: string, notes: string) => void
  requestRevision: (quoteId: string, approverName: string, notes: string) => void
  runDemoScenario: (key: string) => Quote | null
  resetDemo: () => void
  clearActionMessage: () => void
}

function touchQuote(quote: Quote, patch: Partial<Quote>): Quote {
  return { ...quote, ...patch, updatedAt: new Date().toISOString() }
}

let notificationSeq = 0
function notify(text: string): ActionNotification {
  notificationSeq += 1
  return { id: notificationSeq, text }
}

export const useAppStore = create<AppState>((set, get) => ({
  role: 'SALES',
  quotes: [...QUOTES_SEED],
  lastActionMessage: null,

  setRole: (role) => set({ role }),

  clearActionMessage: () => set({ lastActionMessage: null }),

  submitFromCopilot: (context) => {
    const unit = getUnitByCode(context.unitCode)
    if (!unit) throw new Error(`Không tìm thấy căn hộ: ${context.unitCode}`)
    const quote = buildQuoteFromContext({ unit, context })
    set((state) => ({ quotes: [quote, ...state.quotes] }))
    return quote
  },

  sendForReview: (quoteId) => {
    set((state) => ({
      quotes: state.quotes.map((q) => (q.quoteId === quoteId && q.status === 'DRAFT' ? touchQuote(q, { status: 'READY_FOR_REVIEW' }) : q)),
    }))
  },

  approveQuote: async (quoteId, approverName, notes) => {
    const quote = get().quotes.find((q) => q.quoteId === quoteId)
    if (!quote) return

    const approval = buildApprovalRecord({ approverName, decision: 'APPROVED', notes })
    const snapshot = buildSnapshot({ ...quote, approval })
    const snapshotHash = await hashSnapshot(snapshot)
    const signedApproval = { ...approval, signatureHex: snapshotHash }

    set((state) => ({
      quotes: state.quotes.map((q) =>
        q.quoteId === quoteId ? touchQuote(q, { status: 'APPROVED', approval: signedApproval, snapshotHash }) : q,
      ),
      lastActionMessage: notify(`Đã phê duyệt ${quoteId}. Mã băm SHA-256: ${snapshotHash.slice(0, 16)}…`),
    }))
  },

  rejectQuote: (quoteId, approverName, notes) => {
    const approval = buildApprovalRecord({ approverName, decision: 'REJECTED', notes })
    set((state) => ({
      quotes: state.quotes.map((q) => (q.quoteId === quoteId ? touchQuote(q, { status: 'REJECTED', approval }) : q)),
      lastActionMessage: notify(`Đã từ chối ${quoteId}.`),
    }))
  },

  requestRevision: (quoteId, approverName, notes) => {
    const approval = buildApprovalRecord({ approverName, decision: 'NEEDS_REVISION', notes })
    set((state) => ({
      quotes: state.quotes.map((q) => (q.quoteId === quoteId ? touchQuote(q, { status: 'NEEDS_REVISION', approval }) : q)),
      lastActionMessage: notify(`Đã yêu cầu Sale chỉnh sửa ${quoteId}.`),
    }))
  },

  runDemoScenario: (key) => {
    const scenario = getDemoScenario(key)
    if (!scenario) return null
    const context = scenario.buildContext()

    if (scenario.kind === 'CALC_FAILED') {
      const unit = getUnitByCode(context.unitCode)
      if (!unit) return null
      const quote = buildForcedCalculationFailureQuote(unit, context)
      set((state) => ({ quotes: [quote, ...state.quotes], lastActionMessage: notify(`Đã chạy kịch bản: ${scenario.title}`) }))
      return quote
    }

    const quote = get().submitFromCopilot(context)

    if (scenario.kind === 'HAPPY' && quote.status === 'DRAFT') {
      get().sendForReview(quote.quoteId)
      set({ lastActionMessage: notify(`Đã chạy kịch bản: ${scenario.title} — hồ sơ đang chờ Quản lý duyệt.`) })
      return { ...quote, status: 'READY_FOR_REVIEW' }
    }

    if (scenario.kind === 'REJECTED' && quote.status === 'DRAFT') {
      get().sendForReview(quote.quoteId)
      get().rejectQuote(quote.quoteId, 'Hà Nguyễn', scenario.rejectionNote ?? 'Từ chối theo kịch bản diễn tập.')
      set({ lastActionMessage: notify(`Đã chạy kịch bản: ${scenario.title}`) })
      return { ...quote, status: 'REJECTED' }
    }

    set({ lastActionMessage: notify(`Đã chạy kịch bản: ${scenario.title}`) })
    return quote
  },

  resetDemo: () => {
    resetQuoteSequence()
    set({ quotes: [], lastActionMessage: notify('Đã đặt lại toàn bộ dữ liệu demo.') })
  },
}))
