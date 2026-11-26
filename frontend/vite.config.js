import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 前后端分离部署：
//   - 开发：前端 dev server 5173，把 /api 代理到后端 8000
//   - 生产/演示：构建出 dist，由 Nginx 托管（配置见 deploy/nginx.conf），
//     Nginx 把 /api/ 反代到后端 8000；后端不托管前端
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
