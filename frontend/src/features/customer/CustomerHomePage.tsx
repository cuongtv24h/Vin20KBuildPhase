import { ArrowRight, BedDouble, CalendarClock, Gift, MapPin, Maximize2, MessagesSquare } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useProjectOverviews, useUnits } from '@/api/hooks'
import { MoneyText } from '@/components/common/MoneyText'
import { EmptyState, ErrorState, LoadingState } from '@/components/common/PageStates'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { formatDate, formatVnd } from '@/lib/format'

/** Ẩn bản ghi bảng hàng bất thường (giá < 500 triệu) khỏi trang công khai. */
const PUBLIC_MIN_PRICE = 500_000_000
import { cn } from '@/lib/utils'

const BEDROOM_FILTERS = [0, 1, 2, 3] as const

export function CustomerHomePage() {
  const overviews = useProjectOverviews()
  const units = useUnits()
  const [projectId, setProjectId] = useState<string>('ALL')
  const [bedrooms, setBedrooms] = useState<number>(0)

  const visibleUnits = useMemo(
    () =>
      (units.data ?? [])
        .filter((u) => u.listed_price_before_tax_vnd >= PUBLIC_MIN_PRICE && u.status !== 'SOLD')
        .filter((u) => (projectId === 'ALL' || u.project_id === projectId) && (bedrooms === 0 || u.bedrooms === bedrooms))
        .sort((a, b) => Number(a.status !== 'AVAILABLE') - Number(b.status !== 'AVAILABLE') || a.listed_price_before_tax_vnd - b.listed_price_before_tax_vnd),
    [units.data, projectId, bedrooms],
  )

  return (
    <div>
      <section className="border-b border-border/60 bg-gradient-to-b from-white to-transparent">
        <div className="container space-y-3 py-10 sm:py-14">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gold">Mở bán 2026</p>
          <h1 className="max-w-2xl font-display text-3xl font-semibold leading-tight tracking-tight text-primary sm:text-5xl">
            Phương án tài chính phù hợp với vốn của bạn
          </h1>
          <Button asChild size="lg" className="mt-2">
            <Link to="/tu-van">
              <MessagesSquare className="h-4 w-4" /> Tư vấn tài chính
            </Link>
          </Button>
        </div>
      </section>

      <div className="container space-y-10 py-8">
        {overviews.isLoading && <LoadingState />}
        {overviews.error && <ErrorState error={overviews.error} onRetry={() => overviews.refetch()} />}
        {overviews.data?.length === 0 && <EmptyState title="Chưa có dự án mở bán" />}
        {overviews.data && (
          <section className="grid gap-4 md:grid-cols-2">
            {overviews.data.map((o) => (
              <article key={o.project.project_id} className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm">
                <div className="bg-primary px-5 py-4 text-primary-foreground">
                  <h2 className="font-display text-xl font-semibold">{o.project.name}</h2>
                  <p className="mt-0.5 inline-flex items-center gap-1.5 text-sm text-primary-foreground/75">
                    <MapPin className="h-3.5 w-3.5" /> {o.project.location}
                  </p>
                </div>
                <div className="space-y-4 p-5">
                  <p className="text-sm leading-relaxed text-muted-foreground">{o.project.description}</p>
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-muted-foreground">Giá từ</p>
                      <p className="font-semibold tabular-nums">{o.price_from_vnd ? formatVnd(o.price_from_vnd) : '—'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Còn mở bán</p>
                      <p className="font-semibold">{o.available_units} căn</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Bàn giao</p>
                      <p className="inline-flex items-center gap-1 font-semibold">
                        <CalendarClock className="h-3.5 w-3.5" /> {o.project.handover_time}
                      </p>
                    </div>
                  </div>
                  {o.active_policy && (
                    <div className="rounded-lg bg-gold/[0.08] p-3">
                      <p className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-semibold text-gold">
                        <Gift className="h-3.5 w-3.5" /> Ưu đãi áp dụng đến {formatDate(o.active_policy.effective_to)}
                      </p>
                      <ul className="space-y-0.5 text-sm">
                        {o.promotions.slice(0, 4).map((p) => (
                          <li key={p.title}>· {p.title}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </article>
            ))}
          </section>
        )}

        <section className="space-y-4" id="bang-hang">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="font-display text-2xl font-semibold tracking-tight">Bảng hàng</h2>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex rounded-full border border-border bg-white p-0.5 text-sm">
                {[{ id: 'ALL', name: 'Tất cả dự án' }, ...(overviews.data?.map((o) => ({ id: o.project.project_id, name: o.project.name })) ?? [])].map(
                  (p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setProjectId(p.id)}
                      className={cn(
                        'rounded-full px-3 py-1.5 font-medium transition-colors',
                        projectId === p.id ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground',
                      )}
                    >
                      {p.name}
                    </button>
                  ),
                )}
              </div>
              <div className="flex rounded-full border border-border bg-white p-0.5 text-sm">
                {BEDROOM_FILTERS.map((b) => (
                  <button
                    key={b}
                    type="button"
                    onClick={() => setBedrooms(b)}
                    className={cn(
                      'rounded-full px-3 py-1.5 font-medium transition-colors',
                      bedrooms === b ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground',
                    )}
                  >
                    {b === 0 ? 'Mọi loại' : `${b} PN`}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {units.isLoading && <LoadingState />}
          {units.error && <ErrorState error={units.error} onRetry={() => units.refetch()} />}
          {units.data && visibleUnits.length === 0 && <EmptyState title="Không có căn phù hợp bộ lọc" />}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {visibleUnits.map((u) => (
              <Link
                key={u.unit_code}
                to={`/tu-van?can=${u.unit_code}`}
                data-unit={u.unit_code}
                className="group flex flex-col rounded-2xl border border-border bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-display text-lg font-semibold group-hover:text-primary">{u.unit_code}</p>
                    <p className="text-xs text-muted-foreground">
                      {u.project_name} · {u.block}, tầng {u.floor}
                    </p>
                  </div>
                  {u.status === 'RESERVED' && <Badge variant="warning">Đã giữ chỗ</Badge>}
                </div>
                <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <BedDouble className="h-3.5 w-3.5" /> {u.bedrooms} phòng ngủ
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <Maximize2 className="h-3.5 w-3.5" /> {u.area_m2} m²
                  </span>
                  <span>{u.view}</span>
                </div>
                <div className="mt-auto flex items-end justify-between border-t border-border pt-3">
                  <div>
                    <p className="text-xs text-muted-foreground">Giá niêm yết</p>
                    <MoneyText amount={u.listed_price_before_tax_vnd} size="lg" />
                  </div>
                  <span className="inline-flex items-center gap-1 text-sm font-medium text-primary">
                    Tư vấn <ArrowRight className="h-4 w-4" />
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
