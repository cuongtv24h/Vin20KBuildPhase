import { Building, Mail, MapPin, Phone } from 'lucide-react'
import { Link, Outlet } from 'react-router-dom'

export const HOTLINE = '1900 6868'

export function CustomerLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-[hsl(40_33%_98%)]">
      <header className="sticky top-0 z-40 border-b border-border/70 bg-white/90 backdrop-blur">
        <div className="container flex h-16 items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground">
              <Building className="h-4 w-4" />
            </span>
            <span className="leading-tight">
              <span className="block font-display text-lg font-semibold tracking-tight text-primary">VLandFuture</span>
              <span className="block text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Kiến tạo chốn an cư</span>
            </span>
          </Link>
          <nav className="flex items-center gap-1 text-sm">
            <Link to="/" className="hidden rounded-md px-3 py-2 font-medium text-foreground/80 hover:text-primary sm:inline-block">
              Dự án
            </Link>
            <Link to="/tu-van" className="rounded-md px-3 py-2 font-medium text-foreground/80 hover:text-primary">
              Tư vấn tài chính
            </Link>
            <a
              href={`tel:${HOTLINE.replace(/\s/g, '')}`}
              className="inline-flex items-center gap-1.5 rounded-full bg-gold px-3.5 py-2 text-xs font-semibold text-gold-foreground hover:bg-gold/90"
            >
              <Phone className="h-3.5 w-3.5" /> {HOTLINE}
            </a>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="mt-16 bg-primary text-primary-foreground">
        <div className="container grid gap-8 py-10 text-sm sm:grid-cols-3">
          <div className="space-y-2">
            <p className="font-display text-lg font-semibold">VLandFuture</p>
            <p className="text-primary-foreground/70">Công ty Cổ phần Đầu tư Phát triển VLandFuture</p>
          </div>
          <div className="space-y-2 text-primary-foreground/80">
            <p className="flex items-center gap-2">
              <MapPin className="h-4 w-4" /> 72 Lê Thánh Tôn, Phường Bến Nghé, Quận 1, TP. HCM
            </p>
            <p className="flex items-center gap-2">
              <Phone className="h-4 w-4" /> Hotline {HOTLINE}
            </p>
            <p className="flex items-center gap-2">
              <Mail className="h-4 w-4" /> cskh@vlandfuture.vn
            </p>
          </div>
          <div className="space-y-2 sm:text-right">
            <p className="text-xs text-primary-foreground/50">© 2026 VLandFuture. Bảo lưu mọi quyền.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
