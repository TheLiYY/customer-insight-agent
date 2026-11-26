import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 前后端分离部署：
//   - 开发：前端 dev server 5173，把 /api 代理到后端 8000
//   - 生产：dist 单独部署到任意静态服务器（Nginx / scripts/serve_frontend.py），
//     通过 VITE_API_BASE 指定后端地址，后端不再托管前端
export default defineConfig({
  base: '/',
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
