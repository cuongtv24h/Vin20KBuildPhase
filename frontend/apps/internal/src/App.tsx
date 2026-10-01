import { lazy, Suspense, type ComponentType } from 'react'
import { Link, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { IS_DEV_TOOLS_ENABLED } from '@pricepolicy/api-client/config'
import type { UserRole } from '@pricepolicy/api-client/contracts'
import { useAdminSetupStatus } from '@pricepolicy/api-client/hooks'
import { RequireRole } from '@/auth/RequireRole'
import { LoadingState } from '@pricepolicy/ui/components/common/PageStates'
import { StaffLayout } from '@/components/layout/StaffLayout'
import { Toaster } from '@pricepolicy/ui/components/layout/Toaster'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { LoginPage } from '@/features/auth/LoginPage'

/** Tách bundle theo trang. */
function page<K extends string>(loader: () => Promise<Record<K, ComponentType>>, name: K) {
  return lazy(() => loader().then((m) => ({ default: m[name] })))
}

const SalesWorkspacePage = page(() => import('@/features/sale/SalesWorkspacePage'), 'SalesWorkspacePage')
const LeadInboxPage = page(() => import('@/features/sale/LeadInboxPage'), 'LeadInboxPage')
const QuoteFormPage = page(() => import('@/features/sale/QuoteFormPage'), 'QuoteFormPage')
const SaleQuotesPage = page(() => import('@/features/sale/SaleQuotesPage'), 'SaleQuotesPage')
const SaleQuoteDetailPage = page(() => import('@/features/sale/SaleQuoteDetailPage'), 'SaleQuoteDetailPage')
const SaleMessagesPage = page(() => import('@/features/sale/SaleMessagesPage'), 'SaleMessagesPage')
const SalePoliciesPage = page(() => import('@/features/sale/SalePoliciesPage'), 'SalePoliciesPage')
const ApprovalQueuePage = page(() => import('@/features/manager/ApprovalQueuePage'), 'ApprovalQueuePage')
const ApprovalWorkspacePage = page(() => import('@/features/manager/ApprovalWorkspacePage'), 'ApprovalWorkspacePage')
const PolicyListPage = page(() => import('@/features/admin/PolicyListPage'), 'PolicyListPage')
const PolicyDetailPage = page(() => import('@/features/admin/PolicyDetailPage'), 'PolicyDetailPage')
const BenchmarkPage = page(() => import('@/features/admin/BenchmarkPage'), 'BenchmarkPage')
const AdminCpPage = page(() => import('@/features/admin/AdminCpPage'), 'AdminCpPage')
const DevPanel = IS_DEV_TOOLS_ENABLED ? page(() => import('@/components/dev/DevPanel'), 'DevPanel') : null

function StaffArea({ role }: { role: UserRole | UserRole[] }) {
  return (
    <RequireRole role={role}>
      <StaffLayout />
    </RequireRole>
  )
}

function AdminCpRoute() {
  const { data: setupStatus, isLoading } = useAdminSetupStatus()

  if (isLoading) {
    return <LoadingState className="py-32" />
  }

  // Nếu hệ thống chưa khởi tạo Admin ban đầu -> Cho phép mở form khởi tạo trực tiếp
  if (setupStatus && !setupStatus.initialized) {
    return <AdminCpPage />
  }

  // Đã khởi tạo -> bắt buộc đăng nhập với quyền ADMIN và render trong StaffLayout
  return (
    <RequireRole role="ADMIN">
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
        <Link to="/">Về trang đăng nhập</Link>
      </Button>
    </div>
  )
}

/**
 * Cổng nội bộ (Sale, Quản lý, Quản trị chính sách, Quản trị viên hệ thống).
 * Màn hình đăng nhập quy về root ('/'), tùy vai trò sẽ chuyển hướng đến giao diện tương ứng:
 *   Sale (Kinh doanh)             /sale/leads  /sale/quotes  /sale/quotes/new  /sale/quotes/:id
 *   Quản lý kinh doanh (Manager)  /manager/approvals  /manager/approvals/:id
 *   Quản trị chính sách           /admin/policies  /admin/policies/:id  /admin/benchmark
 *   Quản trị viên hệ thống        /admin_cp
 */
function App() {
  return (
    <>
      <Suspense fallback={<LoadingState className="py-32" />}>
        <Routes>
          {/* Màn hình đăng nhập nội bộ tại root '/' và '/login' */}
          <Route path="/" element={<LoginPage />} />
          <Route path="login" element={<LoginPage />} />

          {/* Quản trị viên hệ thống (Admin CP) */}
          <Route path="admin_cp" element={<AdminCpRoute />}>
            <Route index element={<AdminCpPage />} />
          </Route>

          {/* Nhân viên kinh doanh */}
          <Route path="sale" element={<StaffArea role="SALE" />}>
            <Route index element={<Navigate to="workspace" replace />} />
            <Route path="workspace" element={<SalesWorkspacePage />} />
            <Route path="leads" element={<LeadInboxPage />} />
            <Route path="quotes" element={<SaleQuotesPage />} />
            <Route path="quotes/new" element={<QuoteFormPage />} />
            <Route path="quotes/:quoteId" element={<SaleQuoteDetailPage />} />
            <Route path="quotes/:quoteId/revise" element={<QuoteFormPage />} />
            <Route path="messages" element={<SaleMessagesPage />} />
            <Route path="policies" element={<SalePoliciesPage />} />
          </Route>

          {/* Quản lý kinh doanh duyệt báo giá */}
          <Route path="manager" element={<StaffArea role="MANAGER" />}>
            <Route index element={<Navigate to="approvals" replace />} />
            <Route path="approvals" element={<ApprovalQueuePage />} />
            <Route path="approvals/:quoteId" element={<ApprovalWorkspacePage />} />
          </Route>

          {/* Quản trị chính sách (Cho phép cả POLICY_ADMIN và ADMIN) */}
          <Route path="admin" element={<StaffArea role={['POLICY_ADMIN', 'ADMIN']} />}>
            <Route index element={<Navigate to="policies" replace />} />
            <Route path="policies" element={<PolicyListPage />} />
            <Route path="policies/:policyId" element={<PolicyDetailPage />} />
            <Route path="benchmark" element={<BenchmarkPage />} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
        {DevPanel && <DevPanel />}
      </Suspense>
      <Toaster />
    </>
  )
}

export default App
