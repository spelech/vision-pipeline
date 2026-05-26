/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['**/node_modules/**', '**/dist/**', '**/e2e/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'html', 'json-summary'],
      reportsDirectory: './coverage/unit',
      exclude: ['src/test/**', '**/*.d.ts'],
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8460',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost:8460',
        changeOrigin: true,
      }
    }
  }
})
