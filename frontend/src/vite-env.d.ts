/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Origin of the API. Empty in development, where Vite proxies /api. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
