/**
 * Chuẩn hoá JSON theo kiểu RFC 8785 rút gọn: sắp xếp key theo bảng chữ cái ở MỌI cấp độ
 * lồng nhau (đệ quy), đảm bảo cùng dữ liệu đầu vào luôn cho ra cùng chuỗi byte, bất kể thứ
 * tự khai báo field trong object. Không dùng JSON.stringify(value, arrayReplacer) vì
 * replacer dạng mảng chỉ cho phép đúng tập key đó ở MỌI cấp — sẽ xoá sạch field lồng nhau.
 */
export function canonicalJsonStringify(value: unknown): string {
  return JSON.stringify(sortKeysDeep(value))
}

function sortKeysDeep(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortKeysDeep)
  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b))
    const sorted: Record<string, unknown> = {}
    for (const [key, val] of entries) sorted[key] = sortKeysDeep(val)
    return sorted
  }
  return value
}

/**
 * SHA-256 THẬT qua Web Crypto API (crypto.subtle.digest) — không phải hash giả lập.
 * Dùng để băm nội dung JSON Snapshot khi Quản lý phê duyệt báo giá.
 */
export async function sha256Hex(content: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(content)
  const digest = await crypto.subtle.digest('SHA-256', data)
  const bytes = Array.from(new Uint8Array(digest))
  return bytes.map((b) => b.toString(16).padStart(2, '0')).join('')
}

/** SHA-256 của nội dung nhị phân (dùng khi Admin Sale tải lên văn bản chính sách gốc). */
export async function sha256HexOfBuffer(buffer: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}
