import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
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
    noDiscovery: true,
    include: [
      'react',
      'react-dom',
      'react-dom/client',
      'react/jsx-dev-runtime',
      'react/jsx-runtime',
      'react-router-dom',
      'scheduler',
      'clsx',
      'lucide-react',
      'zustand',
      'zustand/middleware',
      'react-hook-form',
      '@hookform/resolvers/zod',
      'zod',
      'recharts',
      '@sentry/react',
      '@tanstack/react-query',
    ],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
