import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '../..', '')
  // The browser talks same-origin; Vite forwards API + WebSocket traffic to the backend.
  // This also makes the app usable from a phone on the LAN (`pnpm dev --host`).
  const target = env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'
  // G7 remote access: Tailscale's https://<pc>.<tailnet>.ts.net name, plus any extra names in .env
  const allowedHosts = ['.ts.net', ...(env.WEB_ALLOWED_HOSTS || '').split(',').map((h) => h.trim()).filter(Boolean)]

  return {
    envDir: '../..',
    plugins: [react(), tailwindcss()],
    preview: { allowedHosts },
    server: {
      allowedHosts,
      proxy: {
        '/api': { target, changeOrigin: true },
        '/health': { target, changeOrigin: true },
        '/ws': { target, ws: true, changeOrigin: true },
      },
    },
  }
})
