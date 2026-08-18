import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

export default {
  plugins: [react()],
  build: {
    sourcemap: false,
    chunkSizeWarningLimit: 600,
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
