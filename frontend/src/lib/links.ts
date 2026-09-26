/** Đường dẫn công khai khách hàng dùng để mở báo giá chính thức. */
export function shareUrlFor(token: string): string {
  return `${window.location.origin}/quote/${token}`
}
