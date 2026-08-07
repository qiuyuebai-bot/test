import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

export const testConfig = {
  globals: true,
  environment: 'jsdom',
  setupFiles: ['./src/test/setup.ts'],
  css: false,
  include: ['src/**/*.{test,spec}.{ts,tsx}'],
  exclude: ['node_modules', 'dist', 'backend'],
  coverage: {
    provider: 'v8',
    reporter: ['text', 'html'],
    include: ['src/**/*.{ts,tsx}'],
    exclude: ['src/**/*.{test,spec}.{ts,tsx}', 'src/test/**', 'src/main.tsx', 'src/vite-env.d.ts'],
    thresholds: {
      lines: 30,
      statements: 30,
      functions: 25,
      branches: 40,
    },
  },
}

export default {
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('../src', import.meta.url)),
    },
  },
  test: testConfig,
}
