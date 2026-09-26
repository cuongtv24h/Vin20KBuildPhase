import type { MockFlags } from '@pricepolicy/api-client/devtools'

/** Cờ điều khiển môi trường mock — sống trong bộ nhớ tiến trình mock-server, dùng chung cho mọi
 * client (cả hai app) vì cả hai gọi cùng một server thật; reset khi khởi động lại tiến trình. */
export const DEFAULT_FLAGS: MockFlags = {
  latency: 'normal',
  fail_rate: 0,
  slow_agent: false,
  drop_sse_once: false,
  expire_replay: false,
  pdf_worker_fail: false,
  time_scale: 1,
}

let flags: MockFlags = { ...DEFAULT_FLAGS }

export const getFlags = (): MockFlags => flags

export function setFlags(patch: Partial<MockFlags>): MockFlags {
  flags = { ...flags, ...patch }
  return flags
}

/** Mốc thời gian nghiệp vụ (agent, PDF worker) theo hệ số của môi trường. */
export const scaled = (ms: number, agent = false) => Math.round(ms * flags.time_scale * (agent && flags.slow_agent ? 3 : 1))

/** Độ trễ mạng ngẫu nhiên cho mỗi request. */
export function networkDelay(): number {
  if (flags.time_scale < 1) return 0
  return flags.latency === 'slow' ? 2_500 + Math.random() * 3_500 : 200 + Math.random() * 600
}
