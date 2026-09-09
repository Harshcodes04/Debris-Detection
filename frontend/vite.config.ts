import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5200,
    // Proxying keeps the frontend origin-agnostic: no CORS config on the
    // backend and no base URL baked into the build.
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
})
