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

/** Ngày hiện tại theo giờ địa phương, định dạng YYYY-MM-DD (dùng làm ngày giao dịch mặc định). */
export function todayIso(date: Date = new Date()): string {
  const yyyy = date.getFullYear()
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const dd = String(date.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

/** "2 giờ trước", "3 ngày trước"... */
export function formatRelative(isoDate: string, now: Date = new Date()): string {
  const diffMs = now.getTime() - new Date(isoDate).getTime()
  const minutes = Math.round(diffMs / 60_000)
  if (minutes < 1) return 'vừa xong'
  if (minutes < 60) return `${minutes} phút trước`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} giờ trước`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days} ngày trước`
  return formatDate(isoDate)
}

/** Che số điện thoại thống nhất: giữ 3 ký tự đầu và 3 ký tự cuối, phần giữa thay bằng "*". */
export function maskPhone(phone: string | null | undefined): string {
  const raw = (phone ?? '').replace(/\s+/g, '')
  if (!raw) return ''
  if (raw.length <= 6) return '*'.repeat(raw.length)
  return `${raw.slice(0, 3)}${'*'.repeat(raw.length - 6)}${raw.slice(-3)}`
}

/** Ghi chú hiển thị: loại bỏ "None"/"null"/"undefined"/rỗng; không còn nội dung thì "Chưa có ghi chú". */
export function formatNote(note: string | null | undefined, fallback = 'Chưa có ghi chú'): string {
  const cleaned = (note ?? '')
    .replace(/\b(None|null|undefined)\b/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
  return cleaned || fallback
}
