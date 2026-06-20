import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 120000,
  expect: {
    timeout: 30000
  },
  use: {
    baseURL: 'http://x8-web:5173'
  }
});
