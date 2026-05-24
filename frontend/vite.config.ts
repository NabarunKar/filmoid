import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      // Allow importing assets from the repo root (e.g., ../Resources/*)
      allow: [resolve(__dirname, '..')],
    },
  },
})
