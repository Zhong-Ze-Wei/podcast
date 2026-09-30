import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    allowedHosts: ['.ts.net'],
    proxy: {
      '/api': {
        // 写死 IPv4：Node 会把 localhost 解析成 ::1，而后端只监听 IPv4 时代理会连不上
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      }
    }
  }
})
