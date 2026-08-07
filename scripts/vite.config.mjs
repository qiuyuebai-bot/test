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
    // This project is route-split already. Eagerly pre-bundling every heavy
    // feature dependency delays the login page and fails on Windows hosts
    // whose parent directories cannot be scanned by esbuild.
    noDiscovery: true,
    include: [],
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
