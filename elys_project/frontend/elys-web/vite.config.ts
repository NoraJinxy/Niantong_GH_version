import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { execSync } from 'node:child_process'

// 调试期版本标识：构建时刻 + git 短 hash（远端打包已剔除 .git，取不到则记 'nogit'）。
// 前端右下角角标显示，部署后一眼可辨「跑的是不是最新代码」，省去反复猜缓存 / 没部署。
const BUILD_TIME = new Date().toISOString()
function gitShortHash(): string {
  try {
    return execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    return 'nogit'
  }
}
const BUILD_HASH = gitShortHash()

export default defineConfig({
  define: {
    __BUILD_TIME__: JSON.stringify(BUILD_TIME),
    __BUILD_HASH__: JSON.stringify(BUILD_HASH),
  },
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
