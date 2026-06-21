import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backend = 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/documents': backend,
      '/ask': backend,
      '/search': backend,
      '/conversations': backend,
      '/health': backend,
      '/ws': { target: backend, ws: true },
    },
  },
})
