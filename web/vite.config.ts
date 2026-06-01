/// <reference types="vitest" />
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

const currentDir = dirname(fileURLToPath(import.meta.url))
const packageJsonPath = resolve(currentDir, 'package.json')
const packageJson = JSON.parse(readFileSync(packageJsonPath, 'utf-8')) as { version?: string }
const appVersion = packageJson.version ?? '0.0.0'
const buildTime = new Date().toISOString()

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(appVersion),
    'import.meta.env.VITE_BUILD_TIME': JSON.stringify(buildTime),
  },
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
        target: 'http://127.0.0.1:8460',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8460',
        changeOrigin: true,
      }
    }
  }
})
