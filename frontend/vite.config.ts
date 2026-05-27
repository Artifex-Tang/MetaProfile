import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api-tech':      { target: 'http://localhost:8001', rewrite: p => p.replace(/^\/api-tech/, '') },
      '/api-project':   { target: 'http://localhost:8002', rewrite: p => p.replace(/^\/api-project/, '') },
      '/api-org':       { target: 'http://localhost:8003', rewrite: p => p.replace(/^\/api-org/, '') },
      '/api-person':    { target: 'http://localhost:8004', rewrite: p => p.replace(/^\/api-person/, '') },
      '/api-scan':      { target: 'http://localhost:8101', rewrite: p => p.replace(/^\/api-scan/, '') },
      '/api-discovery': { target: 'http://localhost:8102', rewrite: p => p.replace(/^\/api-discovery/, '') },
      '/api-topic':     { target: 'http://localhost:8103', rewrite: p => p.replace(/^\/api-topic/, '') },
    },
  },
})
