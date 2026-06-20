import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 120000,
  grepInvert: /Brain continuity saves next step blocker validation and handoff/,
  expect: {
    timeout: 30000
  },
  use: {
    baseURL: 'http://x8-web:5173'
  }
});
