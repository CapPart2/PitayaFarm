import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api/dashboard': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      '/api/alerts': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/api/library': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      '/predict': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/api/csrf/': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/api/translate': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
      '/api/disease-images': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      '/api/user': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
    },
  },
})
