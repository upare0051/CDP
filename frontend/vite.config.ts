import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

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
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // Cube REST API (demo: run Cube locally on :4000)
      '/cubejs-api': {
        target: 'http://localhost:4000',
        changeOrigin: true,
      },
      // Dittofeed dashboard (Journeys). When running the full stack via
      // docker compose, users normally access cdp-main through nginx at
      // http://localhost/ — this proxy is a fallback so /dashboard/*
      // works in `vite dev` mode too. WebSocket upgrade for Next.js HMR.
      '/dashboard': {
        target: 'http://localhost/',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
