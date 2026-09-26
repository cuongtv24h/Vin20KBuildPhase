import { BedDouble, CalendarClock, Gift, MapPin, Maximize2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useProjectOverviews, useUnits } from '@/api/hooks'
import { MoneyText } from '@/components/common/MoneyText'
import { ErrorState, LoadingState } from '@/components/common/PageStates'
import { UnitStatusBadge } from '@/components/common/StatusBadge'
import { formatDate, formatVnd } from '@/lib/format'
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
        .filter((u) => (projectId === 'ALL' || u.projectId === projectId) && (bedrooms === 0 || u.bedrooms === bedrooms))
        .sort((a, b) => Number(a.status !== 'AVAILABLE') - Number(b.status !== 'AVAILABLE') || a.listedPrice - b.listedPrice),
    [units.data, projectId, bedrooms],
  )

  return (
    <div>
      <section className="border-b border-border/60 bg-gradient-to-b from-white to-transparent">
        <div className="container space-y-3 py-10 sm:py-14">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gold">Mở bán 2026</p>
          <h1 className="max-w-2xl font-display text-3xl font-semibold leading-tight tracking-tight text-primary sm:text-5xl">
            Tìm căn hộ phù hợp và nhận báo giá chính thức trong ngày
          </h1>
          <p className="max-w-xl text-muted-foreground">
            Xem giá tham khảo theo từng phương án thanh toán, sau đó đăng ký để chuyên viên gửi báo giá đã được phê duyệt.
          </p>
        </div>
      </section>

      <div className="container space-y-10 py-8">
        {overviews.isLoading && <LoadingState />}
        {overviews.error && <ErrorState error={overviews.error} onRetry={() => overviews.refetch()} />}
        {overviews.data && (
          <section className="grid gap-4 md:grid-cols-2">
            {overviews.data.map((o) => (
              <article key={o.project.projectId} className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm">
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
                      <p className="font-semibold tabular-nums">{o.priceFrom ? formatVnd(o.priceFrom) : '—'}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Còn mở bán</p>
                      <p className="font-semibold">{o.availableUnits} căn</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Bàn giao</p>
                      <p className="inline-flex items-center gap-1 font-semibold">
                        <CalendarClock className="h-3.5 w-3.5" /> {o.project.handoverTime}
                      </p>
                    </div>
                  </div>
                  {o.activePolicy && (
                    <div className="rounded-lg bg-gold/[0.08] p-3">
                      <p className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-semibold text-gold">
                        <Gift className="h-3.5 w-3.5" /> Ưu đãi áp dụng đến {formatDate(o.activePolicy.effectiveTo)}
                      </p>
                      <ul className="space-y-0.5 text-sm">
                        {o.promotions.slice(0, 4).map((p) => (
                          <li key={p.ruleCode}>· {p.title}</li>
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
                {[{ id: 'ALL', name: 'Tất cả dự án' }, ...(overviews.data?.map((o) => ({ id: o.project.projectId, name: o.project.name })) ?? [])].map(
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
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {visibleUnits.map((u) => {
              const disabled = u.status === 'SOLD'
              return (
                <Link
                  key={u.unitCode}
                  to={`/units/${u.unitCode}`}
                  data-unit={u.unitCode}
                  className={cn(
                    'group rounded-2xl border border-border bg-white p-5 shadow-sm transition-shadow hover:shadow-md',
                    disabled && 'pointer-events-none opacity-55',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-display text-lg font-semibold group-hover:text-primary">{u.unitCode}</p>
                      <p className="text-xs text-muted-foreground">
                        {u.projectName} · {u.block}, tầng {u.floor}
                      </p>
                    </div>
                    <UnitStatusBadge status={u.status} />
                  </div>
                  <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      <BedDouble className="h-3.5 w-3.5" /> {u.bedrooms} phòng ngủ
                    </span>
                    <span className="inline-flex items-center gap-1">
                      <Maximize2 className="h-3.5 w-3.5" /> {u.areaM2} m²
                    </span>
                    <span>{u.view}</span>
                  </div>
                  <div className="mt-4 border-t border-border pt-3">
                    <p className="text-xs text-muted-foreground">Giá niêm yết</p>
                    <MoneyText amount={u.listedPrice} size="lg" />
                  </div>
                </Link>
              )
            })}
          </div>
        </section>
      </div>
    </div>
  )
}
