import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

export default {
  plugins: [react()],
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('/react/') || id.includes('react-dom') || id.includes('react-router') || id.includes('@remix-run') || id.includes('scheduler')) {
            return 'react-vendor'
          }
          if (id.includes('recharts') || id.includes('d3-') || id.includes('victory-')) return 'charts'
          if (id.includes('lucide-react')) return 'icons'
          if (id.includes('zustand') || id.includes('@tanstack/react-query')) return 'state'
          if (id.includes('react-hook-form') || id.includes('@hookform') || id.includes('/zod/')) return 'forms'
          if (id.includes('@sentry')) return 'monitoring'
          return 'vendor'
        },
      },
    },
  },
  optimizeDeps: {
    // Keep the entrypoint dependencies explicit while allowing Vite to find
    // CommonJS modules used by lazy-loaded routes (for example lodash in
    // Recharts) and apply the required ESM interop in dev mode.
    include: ['react', 'react-dom', 'react-dom/client', 'zustand'],
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('../src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    // The workspace also contains backend virtualenvs and runtime caches.
    // Watching those directories blocks the first request on Windows.
    watch: {
      ignored: [
        '**/.venv/**',
        '**/venv/**',
        '**/.pnpm-store/**',
        '**/.uv-cache/**',
        '**/backend/**',
        '**/data/**',
        '**/coverage/**',
        '**/playwright-report/**',
      ],
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
}
