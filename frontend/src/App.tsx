import { lazy, Suspense, type ComponentType } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { IS_DEV_TOOLS_ENABLED } from '@/api/config'
import type { UserRole } from '@/api/contracts'
import { RequireRole } from '@/auth/RequireRole'
import { LoadingState } from '@/components/common/PageStates'
import { CustomerLayout } from '@/components/layout/CustomerLayout'
import { StaffLayout } from '@/components/layout/StaffLayout'
import { Toaster } from '@/components/layout/Toaster'
import { Button } from '@/components/ui/button'
import { LoginPage } from '@/features/auth/LoginPage'

/** Tách bundle theo trang — khách hàng không tải mã khu vực nội bộ và ngược lại. */
function page<K extends string>(loader: () => Promise<Record<K, ComponentType>>, name: K) {
  return lazy(() => loader().then((m) => ({ default: m[name] })))
}

const AdvisorPage = page(() => import('@/features/customer/AdvisorPage'), 'AdvisorPage')
const CustomerHomePage = page(() => import('@/features/customer/CustomerHomePage'), 'CustomerHomePage')
const LeadInboxPage = page(() => import('@/features/sale/LeadInboxPage'), 'LeadInboxPage')
const QuoteFormPage = page(() => import('@/features/sale/QuoteFormPage'), 'QuoteFormPage')
const SaleQuotesPage = page(() => import('@/features/sale/SaleQuotesPage'), 'SaleQuotesPage')
const SaleQuoteDetailPage = page(() => import('@/features/sale/SaleQuoteDetailPage'), 'SaleQuoteDetailPage')
const ApprovalQueuePage = page(() => import('@/features/manager/ApprovalQueuePage'), 'ApprovalQueuePage')
const ApprovalWorkspacePage = page(() => import('@/features/manager/ApprovalWorkspacePage'), 'ApprovalWorkspacePage')
const PolicyListPage = page(() => import('@/features/admin/PolicyListPage'), 'PolicyListPage')
const PolicyDetailPage = page(() => import('@/features/admin/PolicyDetailPage'), 'PolicyDetailPage')
const BenchmarkPage = page(() => import('@/features/admin/BenchmarkPage'), 'BenchmarkPage')
const DevPanel = IS_DEV_TOOLS_ENABLED ? page(() => import('@/components/dev/DevPanel'), 'DevPanel') : null

function StaffArea({ role }: { role: UserRole }) {
  return (
    <RequireRole role={role}>
      <StaffLayout />
    </RequireRole>
  )
}

function NotFoundPage() {
  return (
    <div className="container flex flex-col items-center gap-3 py-24 text-center">
      <p className="font-display text-5xl font-semibold text-primary">404</p>
      <p className="text-muted-foreground">Trang không tồn tại.</p>
      <Button asChild>
        <Link to="/">Về trang chủ</Link>
      </Button>
    </div>
  )
}

/**
 *   Khách hàng (công khai)  /   /tu-van?can=
 *   Sale                    /sale/leads  /sale/quotes  /sale/quotes/new?dossier=  /sale/quotes/:id  /sale/quotes/:id/revise
 *   Quản lý                 /manager/approvals  /manager/approvals/:id
 *   Quản trị chính sách     /admin/policies  /admin/policies/:id  /admin/benchmark
 */
function App() {
  return (
    <>
      <Suspense fallback={<LoadingState className="py-32" />}>
        <Routes>
          <Route element={<CustomerLayout />}>
            <Route index element={<CustomerHomePage />} />
            <Route path="tu-van" element={<AdvisorPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>

          <Route path="login" element={<LoginPage />} />

          <Route path="sale" element={<StaffArea role="SALE" />}>
            <Route index element={<Navigate to="leads" replace />} />
            <Route path="leads" element={<LeadInboxPage />} />
            <Route path="quotes" element={<SaleQuotesPage />} />
            <Route path="quotes/new" element={<QuoteFormPage />} />
            <Route path="quotes/:quoteId" element={<SaleQuoteDetailPage />} />
            <Route path="quotes/:quoteId/revise" element={<QuoteFormPage />} />
          </Route>

          <Route path="manager" element={<StaffArea role="MANAGER" />}>
            <Route index element={<Navigate to="approvals" replace />} />
            <Route path="approvals" element={<ApprovalQueuePage />} />
            <Route path="approvals/:quoteId" element={<ApprovalWorkspacePage />} />
          </Route>

          <Route path="admin" element={<StaffArea role="POLICY_ADMIN" />}>
            <Route index element={<Navigate to="policies" replace />} />
            <Route path="policies" element={<PolicyListPage />} />
            <Route path="policies/:policyId" element={<PolicyDetailPage />} />
            <Route path="benchmark" element={<BenchmarkPage />} />
          </Route>
        </Routes>
        {DevPanel && <DevPanel />}
      </Suspense>
      <Toaster />
    </>
  )
}

export default App
