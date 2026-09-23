/** Định dạng số nguyên VNĐ kiểu vi-VN: "4.233.600.000 đ" */
export function formatVnd(amount: number): string {
  const sign = amount < 0 ? '-' : ''
  const formatted = new Intl.NumberFormat('vi-VN').format(Math.abs(Math.round(amount)))
  return `${sign}${formatted} đ`
}

/** Định dạng số nguyên VNĐ không kèm đơn vị, dùng cho ô số liệu bảng. */
export function formatNumber(amount: number): string {
  return new Intl.NumberFormat('vi-VN').format(Math.round(amount))
}

/** Định dạng phần trăm kiểu "8,5%". */
export function formatPercent(rate: number): string {
  return `${new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(rate * 100)}%`
}

/** Định dạng ngày kiểu "23/09/2026". */
export function formatDate(isoDate: string): string {
  if (!isoDate) return '—'
  const d = new Date(isoDate)
  if (Number.isNaN(d.getTime())) return isoDate
  return new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(d)
}

/** Định dạng ngày giờ đầy đủ kiểu "23/09/2026 14:30". */
export function formatDateTime(isoDate: string): string {
  if (!isoDate) return '—'
  const d = new Date(isoDate)
  if (Number.isNaN(d.getTime())) return isoDate
  return new Intl.DateTimeFormat('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d)
}

export function truncateHash(hash: string, visible = 10): string {
  if (hash.length <= visible * 2) return hash
  return `${hash.slice(0, visible)}…${hash.slice(-visible)}`
}
