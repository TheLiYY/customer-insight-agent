import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发时把 /api 转发到本地 FastAPI（8000 端口），生产环境由 FastAPI 直接托管 dist
export default defineConfig({
  // 生产构建由 FastAPI 挂载在 /app 下托管，因此资源前缀要跟着改
  base: '/app/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500,
  },
})
