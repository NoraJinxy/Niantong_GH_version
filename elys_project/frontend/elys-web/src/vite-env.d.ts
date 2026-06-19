/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_DATA_API_BASE_URL?: string
  readonly VITE_APP_ORIGIN?: string
  readonly VITE_DATA_ORIGIN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// 构建期注入（见 vite.config.ts 的 define）：调试期版本标识。
declare const __BUILD_TIME__: string
declare const __BUILD_HASH__: string

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}
