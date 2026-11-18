import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '../..', '')
  // The browser talks same-origin; Vite forwards API + WebSocket traffic to the backend.
  // This also makes the app usable from a phone on the LAN (`pnpm dev --host`).
  const target = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    envDir: '../..',
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        '/api': { target, changeOrigin: true },
        '/health': { target, changeOrigin: true },
        '/ws': { target, ws: true, changeOrigin: true },
      },
    },
  }
})
