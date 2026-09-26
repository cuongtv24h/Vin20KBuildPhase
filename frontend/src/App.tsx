import { lazy, Suspense, type ComponentType } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { RequireRole } from '@/auth/RequireRole'
import { CustomerLayout } from '@/components/layout/CustomerLayout'
import { StaffLayout } from '@/components/layout/StaffLayout'
import { Toaster } from '@/components/layout/Toaster'
import { LoadingState } from '@/components/common/PageStates'
import { Button } from '@/components/ui/button'
import { LoginPage } from '@/features/auth/LoginPage'
import type { UserRole } from '@/types/domain'

/** Tách bundle theo trang — khách hàng không tải mã của khu vực nội bộ và ngược lại. */
function page<K extends string>(loader: () => Promise<Record<K, ComponentType>>, name: K) {
  return lazy(() => loader().then((m) => ({ default: m[name] })))
}

const AdminDashboardPage = page(() => import('@/features/admin/AdminDashboardPage'), 'AdminDashboardPage')
const AdminQuoteDetailPage = page(() => import('@/features/admin/AdminQuoteDetailPage'), 'AdminQuoteDetailPage')
const AdminQuotesPage = page(() => import('@/features/admin/AdminQuotesPage'), 'AdminQuotesPage')
const FormulaTestsPage = page(() => import('@/features/admin/FormulaTestsPage'), 'FormulaTestsPage')
const InventoryPage = page(() => import('@/features/admin/InventoryPage'), 'InventoryPage')
const PolicyDetailPage = page(() => import('@/features/admin/PolicyDetailPage'), 'PolicyDetailPage')
const PolicyListPage = page(() => import('@/features/admin/PolicyListPage'), 'PolicyListPage')
const CustomerHomePage = page(() => import('@/features/customer/CustomerHomePage'), 'CustomerHomePage')
const SharedQuotePage = page(() => import('@/features/customer/SharedQuotePage'), 'SharedQuotePage')
const UnitDetailPage = page(() => import('@/features/customer/UnitDetailPage'), 'UnitDetailPage')
const ApprovalQueuePage = page(() => import('@/features/manager/ApprovalQueuePage'), 'ApprovalQueuePage')
const ApprovalReviewPage = page(() => import('@/features/manager/ApprovalReviewPage'), 'ApprovalReviewPage')
const ManagerDashboardPage = page(() => import('@/features/manager/ManagerDashboardPage'), 'ManagerDashboardPage')
const QuoteBuilderPage = page(() => import('@/features/sale/QuoteBuilderPage'), 'QuoteBuilderPage')
const SaleDashboardPage = page(() => import('@/features/sale/SaleDashboardPage'), 'SaleDashboardPage')
const SaleLeadsPage = page(() => import('@/features/sale/SaleLeadsPage'), 'SaleLeadsPage')
const SaleQuoteDetailPage = page(() => import('@/features/sale/SaleQuoteDetailPage'), 'SaleQuoteDetailPage')
const SaleQuotesPage = page(() => import('@/features/sale/SaleQuotesPage'), 'SaleQuotesPage')

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
      <p className="text-muted-foreground">Trang bạn tìm không tồn tại.</p>
      <Button asChild>
        <Link to="/">Về trang chủ</Link>
      </Button>
    </div>
  )
}

/**
 * Bản đồ route theo vai trò — mỗi vai trò có điểm vào riêng:
 *   Khách hàng (công khai)  /            /units/:unitCode        /quote/:shareToken
 *   Nhân viên               /login  → tự chuyển theo vai trò
 *   Sale                    /sale        /sale/leads  /sale/quotes  /sale/quotes/new  /sale/quotes/:id  /sale/quotes/:id/revise
 *   Quản lý                 /manager     /manager/approvals  /manager/approvals/:id
 *   Admin Sale              /admin       /admin/policies[/:id]  /admin/inventory  /admin/quotes[/:id]  /admin/formula-tests
 */
function App() {
  return (
    <>
      <Suspense fallback={<LoadingState className="py-32" />}>
        <Routes>
          <Route element={<CustomerLayout />}>
            <Route index element={<CustomerHomePage />} />
            <Route path="units/:unitCode" element={<UnitDetailPage />} />
            <Route path="quote/:shareToken" element={<SharedQuotePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>

          <Route path="login" element={<LoginPage />} />

          <Route path="sale" element={<StaffArea role="SALE" />}>
            <Route index element={<SaleDashboardPage />} />
            <Route path="leads" element={<SaleLeadsPage />} />
            <Route path="quotes" element={<SaleQuotesPage />} />
            <Route path="quotes/new" element={<QuoteBuilderPage />} />
            <Route path="quotes/:quoteId" element={<SaleQuoteDetailPage />} />
            <Route path="quotes/:quoteId/revise" element={<QuoteBuilderPage />} />
          </Route>

          <Route path="manager" element={<StaffArea role="MANAGER" />}>
            <Route index element={<ManagerDashboardPage />} />
            <Route path="approvals" element={<ApprovalQueuePage />} />
            <Route path="approvals/:quoteId" element={<ApprovalReviewPage />} />
          </Route>

          <Route path="admin" element={<StaffArea role="SALE_ADMIN" />}>
            <Route index element={<AdminDashboardPage />} />
            <Route path="policies" element={<PolicyListPage />} />
            <Route path="policies/:policyId" element={<PolicyDetailPage />} />
            <Route path="inventory" element={<InventoryPage />} />
            <Route path="quotes" element={<AdminQuotesPage />} />
            <Route path="quotes/:quoteId" element={<AdminQuoteDetailPage />} />
            <Route path="formula-tests" element={<FormulaTestsPage />} />
          </Route>

          <Route path="staff" element={<Navigate to="/login" replace />} />
        </Routes>
      </Suspense>
      <Toaster />
    </>
  )
}

export default App
