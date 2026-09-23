import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Forward API calls to the FastAPI backend, so the browser sees one origin (no CORS setup needed).
    proxy: { '/portfolios': 'http://localhost:8000' },
  },
})
