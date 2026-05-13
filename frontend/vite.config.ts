import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// When the dev server runs inside Docker Compose, `localhost` is the container
// itself — use service DNS names. On the host, defaults hit published ports.
const devProxyApi =
  process.env.VITE_DEV_PROXY_API || 'http://localhost:8000'
const devProxyCube =
  process.env.VITE_DEV_PROXY_CUBE || 'http://localhost:4001'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (id.includes('react') || id.includes('react-dom') || id.includes('scheduler')) {
            return 'react-vendor';
          }
          if (id.includes('react-router')) {
            return 'router-vendor';
          }
          if (id.includes('@tanstack/react-query')) {
            return 'query-vendor';
          }
          return 'vendor';
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: devProxyApi,
        changeOrigin: true,
      },
      // Cube REST API — host dev: published port 4001; Docker: cube-api:4000
      '/cubejs-api': {
        target: devProxyCube,
        changeOrigin: true,
      },
      // Dittofeed dashboard (Journeys). When running the full stack via
      // docker compose, users normally access cdp-main through nginx at
      // http://localhost/ — this proxy is a fallback so /dashboard/*
      // works in `vite dev` mode too. WebSocket upgrade for Next.js HMR.
      // In docker, `localhost` resolves to the frontend container itself,
      // so the target is overridable via DASHBOARD_PROXY_TARGET (set to
      // http://cdp-proxy/ in docker-compose so nginx's sub_filter branding
      // overrides still apply).
      '^/dashboard/.+': {
        target: process.env.DASHBOARD_PROXY_TARGET || 'http://localhost/',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
