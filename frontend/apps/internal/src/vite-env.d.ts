/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** mock (mặc định) | real */
  readonly NEXT_PUBLIC_API_MODE?: 'mock' | 'real'
  /** URL tuyệt đối của API — mặc định trỏ tới packages/mock-server (http://localhost:8787/api/v1). */
  readonly NEXT_PUBLIC_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
