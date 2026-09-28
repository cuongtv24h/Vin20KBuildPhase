import { describe, expect, it } from 'vitest'
import { canonicalJsonStringify, sha256Hex } from './hash'

describe('canonicalJsonStringify', () => {
  it('giữ nguyên toàn bộ field lồng nhau, không xoá mất dữ liệu', () => {
    const input = { b: { z: 1, a: 2 }, a: [{ y: 1, x: 2 }] }
    const output = JSON.parse(canonicalJsonStringify(input))
    expect(output).toEqual({ a: [{ x: 2, y: 1 }], b: { a: 2, z: 1 } })
  })

  it('cho cùng chuỗi bất kể thứ tự khai báo key ban đầu', () => {
    const a = { quoteId: 'Q1', unit: { code: 'ZEN', price: 100 } }
    const b = { unit: { price: 100, code: 'ZEN' }, quoteId: 'Q1' }
    expect(canonicalJsonStringify(a)).toBe(canonicalJsonStringify(b))
  })
})

describe('sha256Hex', () => {
  it('sinh mã băm SHA-256 hex 64 ký tự và tất định (cùng input → cùng hash)', async () => {
    const h1 = await sha256Hex('hello-vlandfuture')
    const h2 = await sha256Hex('hello-vlandfuture')
    expect(h1).toHaveLength(64)
    expect(h1).toBe(h2)
    expect(h1).toMatch(/^[0-9a-f]{64}$/)
  })
})
