/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** mock (mặc định) | real */
  readonly NEXT_PUBLIC_API_MODE?: 'mock' | 'real'
  /** Mặc định /api/v1 (dùng proxy của Vite dev server). */
  readonly NEXT_PUBLIC_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
