import { lazy, Suspense, type ComponentType } from 'react'
import { Link, Route, Routes } from 'react-router-dom'
import { LoadingState } from '@pricepolicy/ui/components/common/PageStates'
import { Toaster } from '@pricepolicy/ui/components/layout/Toaster'
import { Button } from '@pricepolicy/ui/components/ui/button'
import { CustomerLayout } from '@/components/layout/CustomerLayout'

function page<K extends string>(loader: () => Promise<Record<K, ComponentType>>, name: K) {
  return lazy(() => loader().then((m) => ({ default: m[name] })))
}

const CustomerHomePage = page(() => import('@/features/customer/CustomerHomePage'), 'CustomerHomePage')
const AdvisorPage = page(() => import('@/features/customer/AdvisorPage'), 'AdvisorPage')

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
 * UI Khách hàng — công khai, không đăng nhập, origin riêng biệt hoàn toàn với UI nội bộ (Sale/
 * Quản lý/Quản trị chính sách). Không có menu hay link nào trỏ sang app nội bộ ở đây; hai bên chỉ
 * trao đổi qua API dùng chung (mục 0 của brief).
 *   /            Bảng hàng + tổng quan dự án
 *   /tu-van?can= Tư vấn tài chính (Pre-Sales), có thể mở thẳng từ 1 căn hộ cụ thể
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
        </Routes>
      </Suspense>
      <Toaster />
    </>
  )
}

export default App
